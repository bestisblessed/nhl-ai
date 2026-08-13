#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
MCDAVID_ID=8478402
# Keep this list aligned with the inclusive backfill range in config.py.
SEASONS=(20222023 20232024 20242025 20252026 20262027)

season_label() {
  local season_id="$1"
  printf '%s-%s' "${season_id:0:4}" "${season_id:4:4}"
}

season_title() {
  printf '%s SEASON' "$(season_label "$1")"
}

echo "=== HEALTH (CURRENT SERVICE STATUS) ==="
curl -fsS "${API_BASE_URL}/health" | jq

echo "=== TOP GOAL SCORER ($(season_title 20222023) TOTAL) ==="
curl -fsS \
  "${API_BASE_URL}/players/most-goals?season_id=20222023" \
  | jq

echo "=== TOP PENALTIES PER MINUTE ($(season_title 20222023), MINIMUM 50 GAMES) ==="
curl -fsS \
  "${API_BASE_URL}/players/penalties-per-minute?season_id=20222023&min_games=50&limit=5" \
  | jq

echo "=== TOP PLAYER POINTS ($(season_title 20222023) TOTAL) ==="
curl -fsS \
  "${API_BASE_URL}/players/leaderboard?season_id=20222023&metric=points&limit=5" \
  | jq

echo "=== TOP PLAYER ASSISTS ($(season_title 20222023) TOTAL) ==="
curl -fsS \
  "${API_BASE_URL}/players/leaderboard?season_id=20222023&metric=assists&limit=5" \
  | jq

echo "=== TOP SHOOTING PERCENTAGE ($(season_title 20222023), MINIMUM 50 GAMES) ==="
curl -fsS \
  "${API_BASE_URL}/players/leaderboard?season_id=20222023&metric=shooting_pct&min_games=50&limit=5" \
  | jq

echo "=== TOP TEAMS BY GOALS ($(season_title 20222023)) ==="
curl -fsS \
  "${API_BASE_URL}/teams/rankings?season_id=20222023&metric=goals&limit=5" \
  | jq

echo "=== TOP TEAMS BY SHOTS ($(season_title 20222023)) ==="
curl -fsS \
  "${API_BASE_URL}/teams/rankings?season_id=20222023&metric=shots&limit=5" \
  | jq

echo "=== PIPELINE STATUS (LATEST RUN, MAY COVER MULTIPLE SEASONS) ==="
curl -fsS "${API_BASE_URL}/pipeline/status" | jq

echo "=== FINAL REGULAR-SEASON STANDINGS (2025-2026) ==="
curl -fsS "${API_BASE_URL}/standings?season_id=20252026" | jq

# Playoff champions are not part of the regular-season standings table.
# These are the completed seasons represented by the configured dataset range.
echo "=== STANLEY CUP WINNERS (COMPLETED DATASET SEASONS, CHRONOLOGICAL) ==="
printf '%s\n' \
  '{"season":"2022-2023","winner":"Vegas Golden Knights","abbreviation":"VGK"}' \
  '{"season":"2023-2024","winner":"Florida Panthers","abbreviation":"FLA"}' \
  '{"season":"2024-2025","winner":"Florida Panthers","abbreviation":"FLA"}' \
  '{"season":"2025-2026","winner":"Carolina Hurricanes","abbreviation":"CAR"}' \
  | jq -s

echo "=== CONNOR MCDAVID GOALS BY AVAILABLE SEASON (MULTI-SEASON) ==="
mcdavid_rows=()
for season_id in "${SEASONS[@]}"; do
  season_name="$(season_label "$season_id")"
  row="$(curl -fsS "${API_BASE_URL}/players/most-goals?season_id=${season_id}&limit=100" \
    | jq -c --arg season "$season_name" --argjson player_id "$MCDAVID_ID" '
        first(.[] | select(.player_id == $player_id) | {
          season: $season,
          season_id: ($season | gsub("-"; "") | tonumber),
          player: .name,
          goals: .goals
        }) // {
          season: $season,
          season_id: ($season | gsub("-"; "") | tonumber),
          player: "Connor McDavid",
          goals: null,
          note: "no player-season row returned"
        }')"
  mcdavid_rows+=("$row")
done
printf '%s\n' "${mcdavid_rows[@]}" | jq -s 'sort_by(.season_id)'
