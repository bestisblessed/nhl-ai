# NHL Pipeline File Guide

The package is organized by responsibility: `ingestion/` contains source retrieval and run orchestration, `storage/` contains database code, and `utils/` contains shared low-level helpers.

## Project and deployment files

- `COMMANDS.md` — Documents the shell commands used to install, test, run, and operate the project.
- `README.md` — Explains the architecture, data sources, setup, validation rules, and usage.
- `pyproject.toml` — Defines the Python package, dependencies, optional API/PostgreSQL/test dependencies, and pytest configuration.
- `Dockerfile` — Builds the Python application container and starts the FastAPI server.
- `docker-compose.yml` — Runs the FastAPI service alongside PostgreSQL.

## Root-level application files

- `config.py` — Loads environment configuration and validates season IDs, database settings, and refresh parameters.
- `main.py` — Provides the command-line interface for `seed`, `backfill`, and `refresh`.

### `ingestion/`

- `client.py` — Shared NHL HTTP client.
- `seed.py` — Supplied CSV importer.
- `skaters.py` — Skater and TOI ingestion.
- `games.py` — Schedule and score ingestion.
- `teams.py` — Team-season and team-game ingestion.
- `rosters.py` — Current and historical roster ingestion.
- `standings.py` — Dated standings ingestion.
- `seasons.py` — Contiguous season generation and validation.
- `records.py` — Parsed endpoint DTOs.
- `pipeline.py` — End-to-end ingestion orchestration.

### `storage/`

- `db.py` — SQLAlchemy engine, schema creation, and transaction sessions.
- `models.py` — SQLAlchemy database tables.
- `persistence.py` — Idempotent database upserts.

### `utils/`

- `http.py` — Compatibility adapter for client responses.
- `stats.py` — NHL Stats REST pagination and numeric helpers.

## API service

- `api/routes.py` — Creates the FastAPI application and exposes routes for goal leaders, penalty rates, team rankings, multi-team players, rosters, health, and pipeline status.

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
main.py
    → ingestion/pipeline.py
        → ingestion/client.py / skaters.py / games.py / teams.py / rosters.py / standings.py
            → storage/persistence.py
                → storage/models.py / storage/db.py
                    → PostgreSQL or SQLite
```

Current caveat: roster and standings parsing is organized and tested, but those records still need to be wired into the main database persistence path.
