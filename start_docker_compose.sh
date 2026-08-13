#!/bin/bash

### Docker/PostgreSQL process ###

### Your .env currently points to the Compose hostname db, so use Docker for that configuration
docker compose build
docker compose up -d db

### Run the initial full load
docker compose run --rm api python -m nhl_pipeline backfill

### Start the API service:
docker compose up -d api

### Tests
curl http://localhost:8000/health
curl "http://localhost:8000/players/most-goals?season_id=20222023"
