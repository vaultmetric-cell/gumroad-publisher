#!/usr/bin/env bash
# publish.sh - One-command Gumroad Auto-Publisher runner
#
# Usage:
#   ./publish.sh                     # patch bump, publish live
#   ./publish.sh --bump minor        # minor version bump
#   ./publish.sh --version 2.0.0    # explicit version
#   ./publish.sh --dry-run          # build ZIP only, no API calls
#   ./publish.sh --skip-upload      # update metadata only
#   ./publish.sh --unpublish        # save as draft
#   ./publish.sh --watch            # auto-rebuild on file changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [[ -f ".env" ]]; then
    set -a
    source ".env"
    set +a
    echo "[publish.sh] Loaded .env"
fi

# Verify token
if [[ -z "${GUMROAD_API_TOKEN:-}" ]]; then
    echo "ERROR: GUMROAD_API_TOKEN is not set."
    echo "  Option 1: export GUMROAD_API_TOKEN='your_token_here'"
    echo "  Option 2: add GUMROAD_API_TOKEN=your_token_here to a .env file"
    exit 1
fi

# Check Python
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: Python 3 not found. Install Python 3.9+ and try again."
    exit 1
fi

# Auto-install dependencies if needed
if ! "$PYTHON" -c "import requests, yaml, jinja2" &>/dev/null 2>&1; then
    echo "[publish.sh] Installing dependencies..."
    "$PYTHON" -m pip install -q -r requirements.txt
fi

# Run the publisher
echo "[publish.sh] Starting Gumroad Auto-Publisher..."
"$PYTHON" -m gumroad_publisher "$@"
