#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export SEED_CSV_PATH="${SEED_CSV_PATH:-data/data_dump.csv}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/nhl-ai.db}"
python main.py refresh
