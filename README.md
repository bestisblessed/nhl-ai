# NHL Take-Home Pipeline

This implementation keeps every contiguous regular season from the supplied 2022-23 seed through the configured 2026-27 target. NHL JSON is the primary source; Hockey Reference remains optional reconciliation.

## Run locally

```bash
python -m pip install -e '.[api,test]'
python main.py backfill --offline-seed-only
uvicorn api.routes:app --reload
python -m pytest
```

The offline command proves the required seed-to-database path without network access. A full `backfill` loads 2023-24 through the configured target using NHL Stats REST. `refresh` is the scheduled incremental entry point: each morning it rechecks D-1 through D-3 (with a capped missed-run recovery window), refreshes current-season aggregates, and snapshots standings and current rosters.

## Source mapping

The repository intentionally keeps the Python modules at the project root: `ingestion/` contains source retrieval and parsing; `storage/` owns SQLAlchemy models, sessions, and upserts; `utils/` contains shared helpers; `api/` contains FastAPI routes; and `main.py` is the CLI entry point.

`ingestion/client.py` owns HTTP behavior; `ingestion/skaters.py` handles player reports; `ingestion/games.py` handles schedules and scores; `ingestion/teams.py` handles team reports; `ingestion/rosters.py` and `ingestion/standings.py` handle the corresponding web endpoints; and `ingestion/pipeline.py` coordinates the run.

`skater/summary` supplies player IDs, names, teams, positions, games, goals, assists, points, plus/minus, PIM, special-team goals/points, shots, percentages, and season IDs. `skater/timeonice` supplies TOI and shifts. `/stats/rest/en/game` supplies one canonical row per game. `team/summary?isGame=true` supplies two team-perspective rows per completed game and is the source for exact team goals/shots rankings. Web score, dated standings, and roster endpoints provide mutable daily state.

The supplied CSV contains only skater aggregates for 2022-23. Its comma-separated team field is retained for multi-team reporting; it is never used to attribute aggregate goals or shots to a team.

## Validation guarantees

- Contiguous season discovery fails on a missing intermediate year.
- Seed import validates 24 positional columns, 951 unique players, and literal `None` semantics.
- Full report retrieval validates `total` and falls back to 100-row pagination.
- 2026-27 may have an empty statistics response while it has no final regular-season games.
- Once a final game exists, empty statistics are a hard failure.
- Composite keys make repeated imports and refreshes idempotent.

## Architecture

```mermaid
flowchart LR
  CSV[2022-23 seed CSV] --> Import[Seed importer]
  Stats[NHL Stats REST] --> Client[Shared HTTP client]
  Web[NHL Web API] --> Client
  Client --> Parse[Endpoint parsers]
  Import --> DB[(PostgreSQL / SQLite)]
  Parse --> DB
  DB --> API[FastAPI assignment routes]
  Cron[Daily refresh] --> API
```

Docker Compose provides PostgreSQL and the FastAPI service. No commit or remote publication is performed by this worktree task.
