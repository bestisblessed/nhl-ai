#!/bin/bash

echo "=== HEALTH ==="
curl -sS http://localhost:8000/health | jq

echo "=== TOP GOAL SCORER ==="
curl -sS \
  "http://localhost:8000/players/most-goals?season_id=20222023" \
  | jq

echo "=== TOP TEAMS BY GOALS ==="
curl -sS \
  "http://localhost:8000/teams/rankings?season_id=20222023&metric=goals&limit=5" \
  | jq

echo "=== TOP TEAMS BY SHOTS ==="
curl -sS \
  "http://localhost:8000/teams/rankings?season_id=20222023&metric=shots&limit=5" \
  | jq

echo "=== MULTI-TEAM PLAYERS ==="
curl -sS \
  "http://localhost:8000/players/multi-team?season_id=20222023" \
  | jq 'length'

echo "=== TAMPA BAY ROSTER COUNT ==="
curl -sS \
  "http://localhost:8000/rosters/current/TBL" \
  | jq 'length'

echo "=== PIPELINE STATUS ==="
curl -sS http://localhost:8000/pipeline/status | jq

