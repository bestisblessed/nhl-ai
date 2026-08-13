#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

log() {
  printf '[nhl-stop] %s\n' "$*"
}

command -v docker >/dev/null 2>&1 || {
  log "Docker is not installed or is not on PATH."
  exit 1
}
docker info >/dev/null
docker compose config --quiet

log "Stopping the API and PostgreSQL containers."
docker compose down --remove-orphans

log "NHL pipeline is stopped. The PostgreSQL nhl-data volume was retained."
docker compose ps --all
