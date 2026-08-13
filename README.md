# NHL Take-Home Pipeline

This implementation keeps every contiguous regular season from the supplied 2022-23 seed through the configured 2026-27 target. NHL JSON is the primary source.

## Run locally

```ba
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

Docker Compose provides PostgreSQL and the FastAPI service.

## Database schema design

The schema separates stable entities, season aggregates, game facts, mutable daily snapshots, and operational metadata. NHL player and game IDs are retained as source identifiers. Composite primary keys make imports and refreshes idempotent.

| Table | Grain and key | Purpose |
|---|---|---|
| `seasons` | One row per `(season_id, game_type_id)` | Tracks contiguous season coverage and ingestion state |
| `players` | One row per `player_id` | Stores stable player identity and current attributes |
| `player_season_stats` | One row per `(player_id, season_id, game_type_id)` | Stores season totals used by player leaderboards |
| `games` | One row per `game_id` | Stores canonical schedule, status, teams, venue, and score |
| `player_game_stats` | One row per `(game_id, player_id, team_id)` | Stores player game facts used by incremental correction runs |
| `team_game_stats` | One row per `(game_id, team_id)` | Stores each team's goals, shots, opponent, and result for a game |
| `team_season_stats` | One row per `(season_id, team_id, game_type_id)` | Stores current team-season aggregates |
| `standings_snapshots` | One row per `(season_id, game_type_id, snapshot_date, team_id)` | Preserves dated standings |
| `roster_snapshots` | One row per `(snapshot_date, team_id, player_id)` | Preserves dated active rosters |
| `pipeline_runs` | One row per `run_id` | Records refresh status, timing, counts, and errors |

`player_season_stats` and `player_game_stats` reference `players`; `team_game_stats` and `player_game_stats` reference `games`; and `roster_snapshots` references `players`. Team IDs come directly from NHL data and are repeated with abbreviations in fact tables so analyst responses remain simple and auditable.

## API endpoints and examples

Start the stack, then query `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`. Season IDs use the NHL `YYYYZZZZ` form, such as `20222023`.

### `GET /health`

Checks database connectivity.

```bash
curl http://localhost:8000/health
```

```json
{"status":"ok","database":"reachable"}
```

### `GET /players/most-goals`

Returns the top goal scorers for a season. Parameters: `season_id` (default `20222023`) and `limit` (1-100, default `1`).

```bash
curl 'http://localhost:8000/players/most-goals?season_id=20222023&limit=3'
```

```json
[
  {"player_id":8478402,"name":"Connor McDavid","goals":64,"games_played":82},
  {"player_id":8477956,"name":"David Pastrnak","goals":61,"games_played":82},
  {"player_id":8478420,"name":"Mikko Rantanen","goals":55,"games_played":82}
]
```

### `GET /players/penalties-per-minute`

Ranks players by penalty minutes divided by total time on ice. Parameters: `season_id`, `min_games`, and `limit`. Players without positive time on ice are excluded.

```bash
curl 'http://localhost:8000/players/penalties-per-minute?season_id=20222023&limit=2'
```

```json
[
  {"player_id":8474190,"name":"Wayne Simmonds","pim":49,"total_toi_minutes":134.08,"pim_per_minute":0.3654},
  {"player_id":8482157,"name":"Will Cuylle","pim":10,"total_toi_minutes":27.83,"pim_per_minute":0.3593}
]
```

### `GET /players/leaderboard`

Returns a player leaderboard for `points`, `assists`, or `shooting_pct`. Parameters: `season_id`, `metric`, `min_games`, and `limit`.

```bash
curl 'http://localhost:8000/players/leaderboard?season_id=20222023&metric=points&limit=2'
```

```json
[
  {"player_id":8478402,"name":"Connor McDavid","season_id":20222023,"games_played":82,"points":153},
  {"player_id":8479318,"name":"Leon Draisaitl","season_id":20222023,"games_played":80,"points":128}
]
```

### `GET /teams/rankings`

Ranks teams by summed game-level `goals` or `shots`. Parameters: `season_id`, `metric`, and `limit`. Team game rows are populated by the NHL backfill rather than the supplied player-only CSV.

```bash
curl 'http://localhost:8000/teams/rankings?season_id=20222023&metric=goals&limit=2'
```

```json
[
  {"team_id":10,"team":"TOR","goals":297},
  {"team_id":22,"team":"EDM","goals":285}
]
```

### `GET /standings`

Returns the latest stored standings snapshot for a season.

```bash
curl 'http://localhost:8000/standings?season_id=20262027'
```

```json
[
  {"season_id":20262027,"snapshot_date":"2026-08-13","rank":1,"team_id":14,"team":"TBL","games_played":0,"wins":0,"losses":0,"overtime_losses":0,"points":0,"goals_for":0,"goals_against":0}
]
```

### `GET /players/multi-team`

Returns players whose season record contains more than one team and reports the implied number of changes.

```bash
curl 'http://localhost:8000/players/multi-team?season_id=20222023'
```

```json
[
  {"player_id":8478569,"name":"Noel Acciari","teams":["STL","TOR"],"team_count":2,"team_changes":1},
  {"player_id":8479315,"name":"Joey Anderson","teams":["CHI","TOR"],"team_count":2,"team_changes":1}
]
```

### `GET /rosters/current/{team_abbrev}`

Returns the latest active roster snapshot for a case-insensitive team abbreviation. Roster snapshots are populated by `refresh`.

```bash
curl http://localhost:8000/rosters/current/TBL
```

```json
[
  {"player_id":8478519,"team":"TBL","position":"C","snapshot_date":"2026-08-13"}
]
```

### `GET /pipeline/status`

Returns the latest incremental refresh status and its row counts. Before the first refresh it returns `{"status":"never_run"}`.

```bash
curl http://localhost:8000/pipeline/status
```

```json
{
  "run_id":"b6e...-...",
  "status":"succeeded",
  "command":"refresh",
  "started_at":"2026-08-13T10:17:03+00:00",
  "completed_at":"2026-08-13T10:17:41+00:00",
  "seasons":[20262027],
  "row_counts":{"games":4,"player_game_stats":210,"team_game_stats":8,"player_season_stats":900,"team_season_stats":32,"standings_snapshots":32,"roster_snapshots":736},
  "error":null
}
```

## Challenges and Tradeoffs
### Reconciling the supplied CSV with the NHL APIs
The supplied CSV contains 2022-23 player-season aggregates, but several analyst questions require data that is not present in that file. Team goals and shots require game-level team statistics, while standings and current rosters require separate NHL endpoints.
I retained the supplied CSV as the deterministic and reproducible seed. Additional NHL data is normalized into related tables without changing the meaning of the original seed records.

### Correctly calculating penalties per minute
Penalty minutes are not directly comparable without accounting for playing time. I converted time on ice into a consistent total-minute value and excluded players with zero recorded time on ice to prevent division-by-zero errors.
I also added a `min_games` filter so analysts can reduce small-sample outliers when interpreting the result.



## AI Usage Disclosure
I used OpenAI Codex as a development assistant during this project. I used Codex to:
- Explore implementation approaches and divide the assignment into manageable milestones.
- Draft portions of the ingestion, persistence, FastAPI, test, Docker, automation, and documentation code.
- Identify edge cases involving pagination, idempotency, incomplete responses, season boundaries, and daily corrections.
- Assist with test generation, error diagnosis, command-line verification, and final review of the repository against the assignment requirements.

### Suggestions I Accepted
I accepted suggestions that aligned with the assignment and that I could independently verify, including:
- Separating ingestion, persistence, API, and configuration responsibilities.
- Using NHL IDs and composite keys to support deterministic, idempotent upserts.
- Validating the supplied CSV's shape, duplicate records, pagination totals, and season continuity.
- Recording pipeline-run status and using an overlapping daily refresh window for operational robustness.
- Testing the complete seed-to-database-to-FastAPI path rather than testing each layer only in isolation.

### Suggestions I Modified
I modified AI-generated suggestions when they were broader than the assignment or did not match the available data. For example:
- I retained the supplied CSV as the deterministic seed instead of making initial data availability depend entirely on live NHL requests.
- I adapted suggested data models to distinguish season aggregates, game-level facts, and dated roster and standings snapshots.
- I kept the existing focused module boundaries while rejecting broader reorganizations that would have made the take-home harder to explain.
- I revised generated tests and documentation to match actual NHL payloads and verified endpoint responses.

### Suggestions I Rejected
I rejected suggestions that introduced unnecessary scope, relied on unsupported data sources, or could not be validated. Examples included:
- Features unrelated to the analyst questions in the assignment.
- Treating comma-separated player team abbreviations as a reliable source for team goals and shots.
- Silently accepting partial NHL responses.
- Adding generalized abstractions that were not used by the requested workflow.
- Committing credentials or making the submitted project depend on access to a private hosted environment.

## Estimated time spent
Approximately 15-20 hours, including data exploration, implementation, Docker and managed PostgreSQL setup, testing, documentation, and verification.
