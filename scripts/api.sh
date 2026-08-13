#!/usr/bin/env bash
set -euo pipefail

export DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/nhl-ai.db}"
exec uvicorn api.routes:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}"
