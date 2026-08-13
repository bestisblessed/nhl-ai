#!/usr/bin/env bash
set -euo pipefail

PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/nhl-pyc}" python -m compileall -q ingestion storage utils api config.py main.py tests
python -m pytest tests
