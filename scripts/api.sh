#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/nhl-ai.db}"
exec uvicorn api.routes:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}"
