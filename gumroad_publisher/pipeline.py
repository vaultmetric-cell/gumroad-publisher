"""
pipeline.py — The orchestration core.

Runs every stage in order and records a structured publish receipt
(JSON + log) so every run is fully auditable.

Stages:
  1. resolve_version   — bump or set explicit version
  2. build_staging     — copy assets, generate docs
  3. create_zip        — compress & checksum
  4. get_or_create     — Gumroad product upsert
  5. upload_file       — attach ZIP to product
  6. set_published     — flip publish state
  7. write_receipt     — persist run record
  8. save_version      — commit new version to .version file
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from .api_client import GumroadClient, GumroadAPIError
from .config     import GumroadConfig
from .organizer  import build_staging
from .versioning import resolve_version, write_version
from .zipper     import create_zip


# ──────────────────────────────────────────────
#  Pipeline result
# ──────────────────────────────────────────────

class PipelineResult:
    def __init__(self):
        self.success       = False
        self.version       = None
        self.product_id    = None
        self.product_url   = None
        self.zip_path      = None
        self.zip_sha256    = None
        self.is_new        = False
        self.published     = False
        self.duration_secs = 0.0
        self.error         = None

    def to_dict(self) -> dict:
        return {k: str(v) if isinstance(v, Path) else v for k, v in self.__dict__.items()}


# ──────────────────────────────────────────────
#  Main pipeline
# ──────────────────────────────────────────────

def run_pipeline(
    cfg: GumroadConfig,
    logger,
    bump: str         = "patch",
    explicit_version: str = None,
    dry_run: bool     = False,
    skip_upload: bool = False,
) -> PipelineResult:

    result    = PipelineResult()
    started   = datetime.now()
    client    = GumroadClient(cfg.api_token, logger)

    try:
        # ── 1. Version ──────────────────────────────
        logger.info("─── Stage 1/8: Resolve version")
        version = resolve_version(
            cfg.version_file,
            bump=bump,
            explicit=explicit_version,
            logger=logger,
        )
        result.version = str(version)

        # ── 2. Staging directory ────────────────────
        logger.info("─── Stage 2/8: Build staging directory")
        staging_dir = build_staging(cfg.product, cfg.build, version, logger)

        # ── 3. ZIP ──────────────────────────────────
        logger.info("─── Stage 3/8: Create ZIP archive")
        zip_path = create_zip(
            staging_dir,
            cfg.build.output_dir,
            cfg.product.slug,
            version,
            logger,
        )
        result.zip_path = zip_path

        # Read checksum from sidecar
        sidecar = zip_path.with_suffix(".sha256")
        if sidecar.exists():
            result.zip_sha256 = sidecar.read_text().split()[0]

        if dry_run:
            logger.warning("DRY RUN — stopping before Gumroad API calls.")
            result.success = True
            return result

        # ── 4. Product upsert ───────────────────────
        logger.info("─── Stage 4/8: Upsert Gumroad product")
        product_data, is_new = client.get_or_create_product(cfg.product, str(version))
        result.product_id  = product_data.get("id")
        result.product_url = product_data.get("short_url") or product_data.get("url", "")
        result.is_new      = is_new

        # ── 5. Upload file ──────────────────────────
        if not skip_upload:
            logger.info("─── Stage 5/8: Upload ZIP to Gumroad")
            client.upload_file(result.product_id, zip_path, str(version))
        else:
            logger.warning("Stage 5/8: Upload skipped (--skip-upload).")

        # ── 6. Publish ──────────────────────────────
        logger.info(f"─── Stage 6/8: Set publish state → {cfg.product.published}")
        client.set_published(result.product_id, cfg.product.published)
        result.published = cfg.product.published

        # ── 7. Write receipt ────────────────────────
        logger.info("─── Stage 7/8: Write publish receipt")
        result.success = True
        _write_receipt(cfg, result, logger)

        # ── 8. Save version ─────────────────────────
        logger.info("─── Stage 8/8: Commit new version")
        write_version(cfg.version_file, version)
        logger.info(f"Version {version} saved to {cfg.version_file}")

        elapsed = (datetime.now() - started).total_seconds()
        result.duration_secs = round(elapsed, 2)

        logger.info("")
        logger.success(f"{'━'*55}")
        logger.success(f"  ✓  Published: {cfg.product.name} v{version}")
        logger.success(f"  ✓  URL:       {result.product_url}")
        logger.success(f"  ✓  ZIP:       {zip_path.name}")
        logger.success(f"  ✓  Duration:  {elapsed:.1f}s")
        logger.success(f"{'━'*55}")

    except GumroadAPIError as e:
        result.success = False
        result.error   = str(e)
        logger.error(f"Gumroad API error: {e}")
        if e.status_code == 401:
            logger.error("→ Check your GUMROAD_API_TOKEN.")
        elif e.status_code == 422:
            logger.error("→ Validation error — review product config.")
        sys.exit(1)

    except Exception as e:
        result.success = False
        result.error   = str(e)
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    return result


# ──────────────────────────────────────────────
#  Receipt writer
# ──────────────────────────────────────────────

def _write_receipt(cfg: GumroadConfig, result: PipelineResult, logger) -> None:
    receipt_dir  = Path(cfg.build.output_dir) / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    ts           = datetime.now().strftime("%Y%m%d-%H%M%S")
    receipt_path = receipt_dir / f"publish-{cfg.product.slug}-{ts}.json"

    receipt = {
        "session_id":   logger.session_id,
        "timestamp":    datetime.now().isoformat(),
        "product":      cfg.product.name,
        "slug":         cfg.product.slug,
        "version":      result.version,
        "product_id":   result.product_id,
        "product_url":  result.product_url,
        "zip":          str(result.zip_path),
        "sha256":       result.zip_sha256,
        "is_new":       result.is_new,
        "published":    result.published,
        "success":      result.success,
        "error":        result.error,
    }

    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    logger.info(f"Receipt saved: {receipt_path}")
