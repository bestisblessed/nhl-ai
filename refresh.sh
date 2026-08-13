#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

log() {
  printf '[nhl-refresh] %s\n' "$*"
}

show_failure_context() {
  local exit_code=$?
  log "Daily refresh failed (exit ${exit_code}). Current service state:"
  docker compose ps --all || true
  docker compose logs --tail=80 db || true
  exit "$exit_code"
}
trap show_failure_context ERR

command -v docker >/dev/null 2>&1 || {
  log "Docker is not installed or is not on PATH."
  exit 1
}
docker info >/dev/null
docker compose config --quiet

log "Ensuring PostgreSQL is running."
docker compose up -d db

log "Waiting for PostgreSQL readiness."
for attempt in {1..60}; do
  if docker compose exec -T db pg_isready -U nhl -d nhl >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    log "PostgreSQL did not become ready within 60 seconds."
    exit 1
  fi
  sleep 1
done

log "Running the incremental D-1 through D-3 refresh through main.py."
docker compose run --rm api python main.py refresh

trap - ERR
log "Daily refresh completed successfully."
docker compose ps

running_services="$(docker compose ps --status running --services)"
if [[ $'\n'"$running_services"$'\n' == *$'\napi\n'* ]]; then
  log "Verifying the running API after refresh."
  curl --fail --silent --show-error --max-time 5 http://localhost:8000/health
  printf '\n'
fi
