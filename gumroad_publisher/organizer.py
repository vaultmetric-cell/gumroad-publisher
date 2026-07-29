"""
organizer.py — Product folder builder and asset organizer.

Creates a clean, versioned staging directory with:
  /dist/<slug>-v<version>/
    README.md
    CHANGELOG.md
    assets/        ← all source files copied here
    docs/          ← any *.md / *.pdf / *.txt documentation
    extras/        ← anything else (bonus files, scripts, etc.)

Uses Jinja2 templates for README and CHANGELOG generation.
"""

import fnmatch
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import BuildConfig, ProductConfig
from .versioning import Version


# ──────────────────────────────────────────────
#  Template rendering (no hard dependency on Jinja2 at runtime)
# ──────────────────────────────────────────────

def _render_template(template_path: str, context: dict) -> str:
    """
    Try Jinja2 first; fall back to a simple {{key}} substitution if not installed.
    """
    path = Path(template_path)
    if not path.exists():
        return _builtin_readme(context) if "README" in template_path else _builtin_changelog(context)

    raw = path.read_text(encoding="utf-8")
    try:
        from jinja2 import Environment, BaseLoader
        env = Environment(loader=BaseLoader())
        tpl = env.from_string(raw)
        return tpl.render(**context)
    except ImportError:
        # Simple {{var}} substitution fallback
        for k, v in context.items():
            raw = raw.replace("{{" + k + "}}", str(v))
            raw = raw.replace("{{ " + k + " }}", str(v))
        return raw


def _builtin_readme(ctx: dict) -> str:
    tags = ", ".join(ctx.get("tags", []))
    price = ctx.get("price_display", "Free")
    return f"""# {ctx['name']}

> {ctx.get('description', '')}

**Version:** {ctx['version']}  
**Released:** {ctx['date']}  
**Price:** {price}  
**Tags:** {tags}

## What's Included

See the `assets/` folder for all product files and `docs/` for documentation.

## Changelog

See `CHANGELOG.md` for full version history.

---
*Built with the Gumroad Auto-Publisher pipeline.*
"""


def _builtin_changelog(ctx: dict) -> str:
    return f"""# Changelog

## [{ctx['version']}] — {ctx['date']}

### Added
- Initial release of {ctx['name']}

---
*Full changelog maintained across versions.*
"""


# ──────────────────────────────────────────────
#  Asset classification
# ──────────────────────────────────────────────

DOC_EXTENSIONS  = {".md", ".txt", ".pdf", ".rst", ".docx", ".html"}
ASSET_SKIP_DIRS = {"__pycache__", ".git", ".svn", "node_modules", ".idea"}


def _classify(file_path: Path) -> str:
    if file_path.suffix.lower() in DOC_EXTENSIONS:
        return "docs"
    return "assets"


def _should_exclude(file_path: Path, patterns: List[str], base: Path) -> bool:
    rel = str(file_path.relative_to(base)).replace("\\", "/")
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat):
            return True
        # also match any path segment
        for part in file_path.parts:
            if part in ASSET_SKIP_DIRS:
                return True
    return False


# ──────────────────────────────────────────────
#  Main organizer
# ──────────────────────────────────────────────

def build_staging(
    product: ProductConfig,
    build: BuildConfig,
    version: Version,
    logger,
) -> Path:
    """
    Creates a clean staging directory and returns its path.
    The staging dir is: builds/dist/<slug>-v<version>/
    """
    slug        = product.slug
    ver_str     = str(version)
    date_str    = datetime.now().strftime("%Y-%m-%d")
    price_cents = product.price_cents
    price_disp  = "Free" if price_cents == 0 else f"${price_cents / 100:.2f}"

    staging_root = Path(build.output_dir) / "dist" / f"{slug}-v{ver_str}"

    # Wipe any stale staging dir from a previous failed run
    if staging_root.exists():
        logger.warning(f"Removing stale staging dir: {staging_root}")
        shutil.rmtree(staging_root)

    for sub in ("assets", "docs", "extras"):
        (staging_root / sub).mkdir(parents=True, exist_ok=True)

    logger.info(f"Staging dir created: {staging_root}")

    # ── Copy source files ──
    source = Path(build.source_dir)
    if not source.exists():
        logger.warning(f"Source dir not found: {source} — staging with empty assets.")
    else:
        copied = 0
        for file in source.rglob("*"):
            if not file.is_file():
                continue
            if _should_exclude(file, build.exclude_patterns, source):
                logger.debug(f"  Excluded: {file.relative_to(source)}")
                continue

            dest_sub  = _classify(file)
            dest_path = staging_root / dest_sub / file.relative_to(source)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest_path)
            copied += 1
            logger.debug(f"  Copied → {dest_sub}/{file.relative_to(source)}")

        logger.info(f"Copied {copied} file(s) from {source}")

    # ── Generate README ──
    ctx = {
        "name":          product.name,
        "slug":          slug,
        "version":       ver_str,
        "date":          date_str,
        "description":   product.description,
        "tags":          product.tags,
        "price_display": price_disp,
        "currency":      product.currency,
    }
    readme_text = _render_template(build.readme_template, ctx)
    (staging_root / "README.md").write_text(readme_text, encoding="utf-8")
    logger.info("README.md generated.")

    # ── Generate CHANGELOG ──
    # Append to existing CHANGELOG if present, otherwise create
    changelog_path = staging_root / "CHANGELOG.md"
    new_entry       = _render_template(build.changelog_template, ctx)
    existing        = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    changelog_path.write_text(new_entry + existing, encoding="utf-8")
    logger.info("CHANGELOG.md generated.")

    return staging_root
