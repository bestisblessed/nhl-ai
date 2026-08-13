#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/nhl-pyc}" python -m compileall -q ingestion storage utils api config.py main.py tests
python -m pytest -p no:cacheprovider tests
