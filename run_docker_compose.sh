#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

usage() {
  cat <<'EOF'
Usage: ./run_docker_compose.sh {status|start|stop|purge}

  status  Show containers and API health.
  start   Build and start the local PostgreSQL/API stack.
  stop    Stop containers while preserving the PostgreSQL volume.
  purge   Stop containers and delete the PostgreSQL volume and local image.
EOF
}

command -v docker >/dev/null 2>&1 || {
  echo "Docker is not installed or is not on PATH." >&2
  exit 1
}

case "${1:-}" in
  status)
    docker compose ps --all
    printf '\nAPI health:\n'
    curl --fail --silent --show-error --max-time 5 http://localhost:8000/health \
      || echo "API is not currently reachable on port 8000."
    printf '\n'
    ;;
  start)
    docker compose config --quiet
    docker compose up --build -d --wait
    docker compose ps --all
    curl --fail --silent --show-error --max-time 5 http://localhost:8000/health
    printf '\n'
    completed_seasons=""
    if completed_seasons="$(docker compose exec -T db psql -U nhl -d nhl -tAc \
      "SELECT count(*) FROM seasons WHERE game_type_id = 2 AND season_id IN \
       (20222023, 20232024, 20242025, 20252026, 20262027) \
       AND state IN ('seeded', 'complete', 'scheduled');" 2>/dev/null)"; then
      completed_seasons="$(printf '%s' "$completed_seasons" | tr -d '[:space:]')"
    fi
    seed_rows=""
    if [[ "$completed_seasons" == "5" ]]; then
      seed_rows="$(curl --fail --silent --show-error --max-time 10 \
        'http://localhost:8000/players/most-goals?season_id=20222023' || true)"
    fi
    if [[ "$completed_seasons" != "5" || "$seed_rows" == "[]" ]]; then
      echo "Database backfill is missing or incomplete; running the initial historical backfill."
      docker compose run --rm api python main.py backfill
      echo "Initial backfill completed; running the first incremental refresh."
      docker compose run --rm api python main.py refresh
      echo "Initial backfill and refresh completed."
    else
      echo "Existing database detected; skipping initial backfill and refresh."
    fi
    ;;
  stop)
    docker compose down --remove-orphans
    echo "Stopped. PostgreSQL volume nhl-data was preserved."
    ;;
  purge)
    echo "This removes containers, the local PostgreSQL volume, and local Compose images."
    read -r -p "Continue? [y/N] " confirmation
    if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
      echo "Purge cancelled."
      exit 0
    fi
    docker compose down --remove-orphans --volumes --rmi local
    ;;
  *)
    usage
    [[ $# -eq 0 ]] && exit 0
    exit 1
    ;;
esac
