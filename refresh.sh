#!/bin/bash

### This should be ran each morning to update the datasets/backend
docker compose run --rm api python -m nhl_pipeline refresh

### OR if testing locally can uncomment and run this version utilizing SQLite instead:
#SEED_CSV_PATH="$PWD/data/data_dump.csv"
#DATABASE_URL=sqlite:////tmp/nhl-ai.db
#python -m nhl_pipeline refresh
