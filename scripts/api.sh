#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

exec uvicorn api.routes:create_app --factory \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}"
