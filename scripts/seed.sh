#!/usr/bin/env bash
set -euo pipefail

export SEED_CSV_PATH="${SEED_CSV_PATH:-data/data_dump.csv}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/nhl-ai.db}"
python main.py seed
