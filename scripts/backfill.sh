#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export SEED_CSV_PATH="${SEED_CSV_PATH:-data/data_dump.csv}"
python main.py backfill
