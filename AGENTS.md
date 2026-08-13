# NHL Pipeline File Guide

## Project and deployment files

- `COMMANDS.md` — Documents the shell commands used to install, test, run, and operate the project.
- `README.md` — Explains the architecture, data sources, setup, validation rules, and usage.
- `pyproject.toml` — Defines the Python package, dependencies, optional API/PostgreSQL/test dependencies, and pytest configuration.
- `Dockerfile` — Builds the Python application container and starts the FastAPI server.
- `docker-compose.yml` — Runs the FastAPI service alongside PostgreSQL.

## Core package files

- `nhl_pipeline/__init__.py` — Exposes the main public client, seed importer, and skater-ingestion classes.
- `nhl_pipeline/__main__.py` — Provides the command-line interface for `seed`, `backfill`, and `refresh`.
- `nhl_pipeline/config.py` — Loads environment configuration and validates season IDs, database settings, and refresh parameters.
- `nhl_pipeline/db.py` — Creates the SQLAlchemy database engine, schema, and transaction-scoped sessions.
- `nhl_pipeline/models.py` — Defines the SQLAlchemy database tables and relationships for seasons, players, games, teams, rosters, standings, and pipeline runs.
- `nhl_pipeline/seasons.py` — Generates contiguous season IDs and rejects missing or malformed seasons.
- `nhl_pipeline/records.py` — Defines lightweight dataclasses used to represent parsed NHL API records before database persistence.

## HTTP and API clients

- `nhl_pipeline/client.py` — Shared NHL HTTP client with URL encoding, timeouts, retries, exponential backoff, response metadata, SHA-256 hashes, and optional caching.
- `nhl_pipeline/_http.py` — Compatibility adapter that normalizes responses from the shared NHL client for endpoint modules.
- `nhl_pipeline/stats.py` — Provides reusable NHL Stats REST pagination, numeric conversion, and season-filter helpers.

## Data import and ingestion

- `nhl_pipeline/seed.py` — Reads the supplied 24-column CSV while preserving positional blank columns, handling literal `None` values, validating the 2022-23 season, and rejecting duplicate players.
- `nhl_pipeline/skaters.py` — Fetches and normalizes skater season totals, TOI/shifts, and game-level skater statistics.
- `nhl_pipeline/game_team.py` — Retrieves schedules, games, scores, team game logs, and team-season summaries.
- `nhl_pipeline/rosters_standings.py` — Retrieves current/historical rosters and dated standings snapshots.
- `nhl_pipeline/persistence.py` — Converts seed/API records into idempotent SQLAlchemy upserts.
- `nhl_pipeline/pipeline.py` — Acts as the main orchestration layer for seed loading, historical backfills, and daily refreshes.

## API service

- `nhl_pipeline/api.py` — Creates the FastAPI application and exposes routes for goal leaders, penalty rates, team rankings, multi-team players, rosters, health, and pipeline status.

## Tests

- `tests/test_client.py` — Tests HTTP query encoding, caching, retries, and transient-error handling.
- `tests/test_games_rosters_standings.py` — Tests game, team, score, roster, and standings parsers.
- `tests/test_pipeline_acceptance.py` — Tests the seed-to-database-to-FastAPI vertical slice and repeatable schema creation.
- `tests/test_schema.py` — Tests database tables, composite keys, and operational metadata.
- `tests/test_seasons.py` — Tests contiguous season generation and missing-season validation.
- `tests/test_seed.py` — Tests the 951-row CSV import and seed validation rules.
- `tests/test_skaters.py` — Tests skater pagination, normalization, TOI conversion, and incomplete-response failures.

## Main execution flow

```text
__main__.py
    → pipeline.py
        → client.py / skaters.py / game_team.py / rosters_standings.py
            → persistence.py
                → models.py / db.py
                    → PostgreSQL or SQLite
```

One important caveat: `rosters_standings.py` contains the roster and standings ingestion logic, but those records are not yet fully wired into `pipeline.py`'s database persistence path.
