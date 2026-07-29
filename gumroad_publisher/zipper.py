"""
zipper.py — ZIP archive builder.

Takes the staged product directory and produces a clean, versioned ZIP
in the builds/ output directory.  The ZIP internal structure mirrors the
staging directory so buyers get a well-organized download.

Output filename pattern:  <slug>-v<version>.zip
"""

import hashlib
import zipfile
from datetime import datetime
from pathlib import Path

from .versioning import Version


# ──────────────────────────────────────────────
#  Checksum helpers
# ──────────────────────────────────────────────

def _sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ──────────────────────────────────────────────
#  Main zipper
# ──────────────────────────────────────────────

def create_zip(
    staging_dir: Path,
    output_dir: str,
    slug: str,
    version: Version,
    logger,
) -> Path:
    """
    Zip the staging directory.

    Returns the path to the created ZIP file.
    Writes a <slug>-v<version>.sha256 sidecar for integrity verification.
    """
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    zip_name = f"{slug}-v{version}.zip"
    zip_path = out_root / zip_name

    # Remove a previous ZIP for the same version if re-running
    if zip_path.exists():
        logger.warning(f"Overwriting existing ZIP: {zip_path}")
        zip_path.unlink()

    total_files = 0
    total_bytes = 0

    logger.info(f"Building ZIP: {zip_name}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(staging_dir.rglob("*")):
            if not file.is_file():
                continue

            arcname = file.relative_to(staging_dir.parent)   # includes <slug>-vX.Y.Z/ prefix
            zf.write(file, arcname=str(arcname))

            size = file.stat().st_size
            total_bytes += size
            total_files += 1
            logger.debug(f"  Zipped: {arcname}  ({_human_size(size)})")

    zip_size  = zip_path.stat().st_size
    sha256    = _sha256(zip_path)

    # Write checksum sidecar
    sidecar_path = out_root / f"{slug}-v{version}.sha256"
    sidecar_path.write_text(f"{sha256}  {zip_name}\n", encoding="utf-8")

    logger.info(f"ZIP complete: {total_files} files, "
                f"uncompressed {_human_size(total_bytes)}, "
                f"compressed {_human_size(zip_size)}")
    logger.info(f"SHA-256: {sha256}")

    return zip_path


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
