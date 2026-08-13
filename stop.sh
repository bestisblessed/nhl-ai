#!/usr/bin/env bash
set -Eeuo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

project_name="${COMPOSE_PROJECT_NAME:-nhl_takehome_final}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed or is not on PATH." >&2
  exit 1
fi

if [[ ! -f compose.yaml && ! -f compose.yml && ! -f docker-compose.yaml && ! -f docker-compose.yml ]]; then
  echo "Error: no Docker Compose file found in $(pwd)." >&2
  exit 1
fi

docker compose -p "$project_name" down

echo "NHL stack stopped. Database volumes were preserved."
