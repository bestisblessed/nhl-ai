# NHL Take-Home Pipeline

This implementation keeps every contiguous regular season from the supplied 2022-23 seed through the configured 2026-27 target. NHL JSON is the primary source; Hockey Reference remains optional reconciliation.

## Run locally

```bash
./run_docker_compose.sh start
./refresh.sh
```

`run_docker_compose.sh start` builds the local FastAPI/PostgreSQL stack and
automatically runs the initial backfill and first incremental refresh when the
2022-23 seed data is absent. On later starts it detects the existing database
and skips both ingestion steps.

For direct CLI development outside Docker, install the project with
`python -m pip install -e '.[api,test]'` and set `DATABASE_URL` to a reachable
PostgreSQL database first.

`DATABASE_URL` is required for application and CLI runs and must point to
PostgreSQL. The test suite uses explicitly configured temporary SQLite databases
for isolated unit tests; SQLite is not an application fallback.

The offline command proves the required seed-to-database path without network access. A full `backfill` loads 2023-24 through the configured target using NHL Stats REST. `refresh` is the scheduled incremental entry point: each morning it rechecks D-1 through D-3 (with a capped missed-run recovery window), refreshes current-season aggregates, and snapshots standings and current rosters.

The `NHL Daily Refresh` GitHub Actions workflow runs at 06:17 America/New_York every day and
can also be started manually with an optional historical `as_of` date. It connects
to the same durable managed PostgreSQL database used by the deployed API through
the `NHL_DATABASE_URL` GitHub secret. On the first run it detects an empty schema,
performs the contiguous backfill once, and then runs the incremental refresh.
Subsequent runs only refresh PostgreSQL; no SQLite database cache is used.
GitHub only schedules workflows that exist on the repository's default branch.

### Managed PostgreSQL setup (Supabase)

1. The assessment database is configured as the free Supabase project
   `nhl-ai`. Use **Connect -> Direct -> Session pooler -> URI**. The session
   pooler is the IPv4-compatible option required by GitHub-hosted runners.
2. Copy its connection URL. The workflow accepts the provider's standard
   `postgresql://...` form and selects psycopg automatically; the explicit
   equivalent is `postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require`.
3. In GitHub, open **Settings -> Secrets and variables -> Actions**, create a
   repository secret named `NHL_DATABASE_URL`, and paste the connection URL.
4. Manually dispatch **NHL Daily Refresh** once from the branch containing this
   workflow. The empty managed database is backfilled automatically before the
   first incremental refresh.
5. Point any deployed FastAPI service at the same URL through its `DATABASE_URL`
   environment variable. Keep local Docker Compose for development; it continues
   using its own local PostgreSQL volume unless you deliberately override
   `DATABASE_URL` for a managed-database smoke test.

The application always reads `DATABASE_URL`. `NHL_DATABASE_URL` is only the
GitHub Actions secret name; it is not a second database format. For a local
Supabase smoke test, pass the same value as `DATABASE_URL` to the Docker command
without committing it to the repository.

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
  Import --> DB[(Managed PostgreSQL)]
  Parse --> DB
  DB --> API[FastAPI assignment routes]
  Cron[Daily refresh] --> API
```

Docker Compose provides PostgreSQL and the FastAPI service. No commit or remote publication is performed by this worktree task.
