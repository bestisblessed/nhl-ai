#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

log() {
  printf '[nhl-start] %s\n' "$*"
}

show_failure_context() {
  local exit_code=$?
  log "Startup failed (exit ${exit_code}). Current service state:"
  docker compose ps --all || true
  docker compose logs --tail=80 db api || true
  exit "$exit_code"
}
trap show_failure_context ERR

command -v docker >/dev/null 2>&1 || {
  log "Docker is not installed or is not on PATH."
  exit 1
}
docker info >/dev/null
docker compose config --quiet

log "Building the API image."
docker compose build api

log "Starting PostgreSQL."
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

log "Running the idempotent seed and full historical backfill."
docker compose run --rm api python main.py backfill

log "Starting the FastAPI service."
docker compose up -d api

log "Waiting for the API health endpoint."
for attempt in {1..60}; do
  if curl --fail --silent --show-error --max-time 3 http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    log "The API did not become healthy within 60 seconds."
    exit 1
  fi
  sleep 1
done

trap - ERR
log "NHL pipeline is running."
docker compose ps
curl --fail --silent --show-error http://localhost:8000/health
printf '\n'
