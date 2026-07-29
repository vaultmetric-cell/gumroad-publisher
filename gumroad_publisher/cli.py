"""
cli.py — Command-line interface for the Gumroad Auto-Publisher.

Usage:
  python -m gumroad_publisher [OPTIONS]

Options:
  --config PATH          Config file path          [default: gumroad_config.yaml]
  --bump major|minor|patch  Version bump strategy  [default: patch]
  --version X.Y.Z        Set exact version (overrides --bump)
  --dry-run              Build ZIP only, skip all API calls
  --skip-upload          Publish metadata only, skip file upload
  --unpublish            Set product to unpublished state
  --log FILE             Override log file path
  --help                 Show this message and exit
"""

import argparse
import sys
from pathlib import Path

from .config   import load_config
from .logger   import build_logger
from .pipeline import run_pipeline


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gumroad-publisher",
        description="One-command Gumroad product builder and publisher.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config", default="gumroad_config.yaml",
        help="Path to YAML configuration file. (default: gumroad_config.yaml)",
    )
    parser.add_argument(
        "--bump", choices=["major", "minor", "patch"], default="patch",
        help="Semantic version bump type. (default: patch)",
    )
    parser.add_argument(
        "--version", dest="explicit_version", default=None, metavar="X.Y.Z",
        help="Set an explicit version, overriding --bump.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Build and ZIP the product without making any Gumroad API calls.",
    )
    parser.add_argument(
        "--skip-upload", action="store_true",
        help="Update product metadata only; do not upload the ZIP file.",
    )
    parser.add_argument(
        "--unpublish", action="store_true",
        help="Set the product to unpublished after updating.",
    )
    parser.add_argument(
        "--log", dest="log_file", default=None,
        help="Override the log file path from config.",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Watch source_dir for changes and auto-rebuild (dry-run) on every save.",
    )
    parser.add_argument(
        "--watch-interval", dest="watch_interval", type=int, default=5, metavar="SECS",
        help="Polling interval in seconds for --watch mode. (default: 5)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    # Load config
    cfg = load_config(args.config)

    # Apply CLI overrides
    if args.log_file:
        cfg.log_file = args.log_file
    if args.unpublish:
        cfg.product.published = False

    # Start logger
    logger = build_logger(cfg.log_file)

    logger.info(f"Config: {Path(args.config).resolve()}")
    logger.info(f"Product: {cfg.product.name!r}  Slug: {cfg.product.slug!r}")
    logger.info(f"Source: {cfg.build.source_dir}  →  Output: {cfg.build.output_dir}")

    if args.dry_run:
        logger.warning("DRY RUN mode — no Gumroad API calls will be made.")

    # Watch mode (dry-run rebuild on every file save)
    if args.watch:
        from .watcher import run_watch_mode
        logger.info(f"Watch mode: interval={args.watch_interval}s, dry_run=True")
        run_watch_mode(cfg, logger, interval=args.watch_interval)
        return

    # Run the pipeline
    run_pipeline(
        cfg=cfg,
        logger=logger,
        bump=args.bump,
        explicit_version=args.explicit_version,
        dry_run=args.dry_run,
        skip_upload=args.skip_upload,
    )


if __name__ == "__main__":
    main()
