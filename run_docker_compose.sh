#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

usage() {
  cat <<'EOF'
Usage: ./nhl_docker_control.sh {status|start|stop|purge}

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
