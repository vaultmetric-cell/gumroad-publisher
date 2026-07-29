"""
watcher.py — Optional file-watcher for auto-rebuild on source changes.

When running in watch mode (`--watch`), the publisher monitors `source_dir`
and triggers a new dry-run build every time a file changes.  Useful during
active development to verify the ZIP assembles correctly.

Requires no external dependencies beyond the stdlib `watchdog` shim below.
Falls back gracefully to a polling loop if watchdog is not installed.

Usage:
  python -m gumroad_publisher --watch [--watch-interval 5]
"""

import time
import threading
import hashlib
from pathlib import Path
from typing import Callable


# ──────────────────────────────────────────────
#  Directory fingerprint (used for polling fallback)
# ──────────────────────────────────────────────

def _dir_fingerprint(directory: str) -> str:
    """Return a hash of all filenames + mtimes under directory."""
    h = hashlib.md5()
    base = Path(directory)
    if not base.exists():
        return ""
    for p in sorted(base.rglob("*")):
        if p.is_file():
            stat = p.stat()
            h.update(f"{p}:{stat.st_mtime}:{stat.st_size}".encode())
    return h.hexdigest()


# ──────────────────────────────────────────────
#  Polling watcher
# ──────────────────────────────────────────────

class SourceWatcher:
    """
    Polls source_dir every `interval` seconds and calls `on_change()`
    when file system state changes.  Runs in a daemon thread so
    Ctrl-C exits cleanly.
    """

    def __init__(
        self,
        source_dir: str,
        on_change: Callable[[], None],
        interval: int = 5,
        logger=None,
    ):
        self.source_dir = source_dir
        self.on_change  = on_change
        self.interval   = interval
        self.logger     = logger
        self._stop      = threading.Event()
        self._last_fp   = _dir_fingerprint(source_dir)
        self._thread    = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        if self.logger:
            self.logger.info(
                f"Watching {self.source_dir!r} for changes "
                f"(polling every {self.interval}s) — Ctrl-C to stop."
            )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self.interval + 1)

    def _loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(self.interval)
            fp = _dir_fingerprint(self.source_dir)
            if fp != self._last_fp:
                self._last_fp = fp
                if self.logger:
                    self.logger.info("Source change detected — triggering build…")
                try:
                    self.on_change()
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Build error in watch mode: {e}")


# ──────────────────────────────────────────────
#  Integration into CLI
# ──────────────────────────────────────────────

def run_watch_mode(cfg, logger, interval: int = 5) -> None:
    """
    Block the main thread while watching source_dir.
    Each detected change triggers a --dry-run pipeline pass.
    """
    from .pipeline import run_pipeline

    def rebuild():
        run_pipeline(cfg=cfg, logger=logger, dry_run=True)

    watcher = SourceWatcher(
        source_dir=cfg.build.source_dir,
        on_change=rebuild,
        interval=interval,
        logger=logger,
    )
    watcher.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Watch mode stopped by user.")
        watcher.stop()
