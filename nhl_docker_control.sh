#!/bin/bash

set -euo pipefail

## Check if containers are running
# ./nhl_docker_control.sh status

## Stop
# ./nhl_docker_control.sh stop

## Start:
# ./nhl_docker_control.sh start

## Fully remove project containers, database volume, and project images
# ./nhl_docker_control.sh purge

PROJECT="nhl_takehome_final"

case "${1:-status}" in
  status)
    echo "Running containers:"
    docker compose -p "$PROJECT" ps -a
    echo
    echo "API health:"
    curl --fail --silent http://localhost:8000/health || echo "API is not currently reachable on port 8000."
    ;;

  stop)
    echo "Stopping API/database and removing project containers/network..."
    echo "The PostgreSQL data volume will be preserved."
    docker compose -p "$PROJECT" down
    ;;

  start)
    echo "Starting the stack..."
    docker compose -p "$PROJECT" up --build -d --wait
    docker compose -p "$PROJECT" ps -a
    ;;

  purge)
    echo "Removing the project containers, network, PostgreSQL data volume, and project images..."
    echo "This deletes the generated local database data, but not your repository files or CSV."
    docker compose -p "$PROJECT" down -v --rmi local
    docker image rm nhl-takehome-audit-api:latest 2>/dev/null || true
    docker image prune -f
    ;;

  *)
    echo "Usage: $0 {status|start|stop|purge}"
    exit 1
    ;;
esac
