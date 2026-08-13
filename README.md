# NHL Analytics API

A small, reproducible service that replaces a manual CSV-to-Excel workflow with validated ingestion,
PostgreSQL storage, and analyst-focused FastAPI endpoints.

## Quick start

Prerequisite: Docker Desktop with Docker Compose.

```bash
docker compose up --build
```

Wait for `api` to become healthy, then open:

- Swagger UI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

The first startup creates PostgreSQL, validates and loads the bundled CSV, then starts the API. The
ingestion container exits successfully after loading 951 rows; that is expected.

```bash
# Stop containers but preserve the database volume
docker compose down

# Optional full reset of this project's generated database volume
docker compose down -v
```

## Architecture

```text
data/data_dump.csv (read-only mount)
              |
              v
     one-shot ingest service ---> PostgreSQL <--- FastAPI
                                      ^              |
                                      |              v
                                health check     JSON / Swagger
```

Compose waits for PostgreSQL health, requires ingestion to finish successfully, and only then starts
the API. The API and ingestion command use the same Python image and database model.

## Database design

`player_season_stats` is one intentionally denormalized analytics table. Its composite primary key is
`(player_id, season)`. It stores player identity, the original team sequence, derived `final_team` and
`team_count`, position, and the independent source statistics needed by the API.

One table is proportional for a 951-row, single-season aggregate snapshot. Separate player, team, and
team-stint tables would add joins without creating the missing team-level splits. A production system
with multiple seasons and sources would likely normalize those dimensions and add migrations.

## Ingestion and cleaning

The loader validates the complete source before replacing the included season in one transaction.
Running it again is idempotent:

```bash
docker compose run --rm ingest
```

Key decisions:

- Require the exact 24-position CSV header and unique `(playerId, Season)` keys.
- Drop two unnamed blank columns, empty `Shifts/GP`, and redundant `MinPerGP`.
- Convert literal `None` percentages to SQL null and validate valid percentage ranges.
- Remove a non-printable control character from one display name while preserving `playerId` as the
  authoritative identity.
- Preserve the comma-separated team sequence; derive its token count and final token.
- Enforce scoring identities and stable domain constraints before writing.

The complete contract is in [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md).

## API endpoints

All analytical endpoints default to season `20222023`. Leaderboards accept a bounded `limit`; player
rate routes also accept `min_games`.

### Health

```bash
curl -s http://localhost:8000/health
```

```json
{"status":"ok","database":"connected","rows_loaded":951}
```

### Goal leaders

```bash
curl -s "http://localhost:8000/players/goals-leaders?limit=1"
```

```json
[{"rank":1,"player_id":8478402,"name":"Connor McDavid","team_codes":["EDM"],"position":"C","games_played":82,"goals":64}]
```

### Penalty-minutes rate leaders

```bash
curl -s "http://localhost:8000/players/penalty-rate-leaders?limit=1&min_games=10"
```

```json
[{"rank":1,"player_id":8474190,"name":"Wayne Simmonds","team_codes":["TOR"],"games_played":18,"penalty_minutes":49,"total_ice_minutes":134.083,"penalty_minutes_per_minute":0.365444,"penalty_minutes_per_60":21.926665}]
```

The source contains penalty minutes, not a count of penalty events. The calculation is
`PIM / (GP * SecPerGP / 60)`; `min_games=10` avoids ranking the smallest samples by default.

### Players appearing for the most teams

```bash
curl -s "http://localhost:8000/players/team-changes?limit=2"
```

```json
[{"rank":1,"player_id":8478211,"name":"Dryden Hunt","team_codes":["NYR","COL","TOR"],"team_count":3,"team_changes":2},{"rank":1,"player_id":8479591,"name":"Michael Eyssimont","team_codes":["WPG","SJS","TBL"],"team_count":3,"team_changes":2}]
```

`team_changes` is inferred as `team_count - 1`; the CSV does not contain transaction dates.

### Inferred season-end roster

```bash
curl -s "http://localhost:8000/teams/TBL/roster"
```

Representative excerpt from the verified response (the actual `players` array contains 26 entries):

```json
{"team_code":"TBL","season":20222023,"is_inferred":true,"inference":"Season-end roster inferred from each player's final listed team; this is not an official current roster.","player_count":26,"players":[{"player_id":8479591,"name":"Michael Eyssimont","position":"C","games_played":54,"team_codes":["WPG","SJS","TBL"]}]}
```

The response explains that the final team token is its basis. It is not a current or official roster.

### Partial team rankings

```bash
curl -s "http://localhost:8000/teams/rankings?metric=goals"
```

Representative excerpt from the verified response (the actual `teams` array contains all 32 teams):

```json
{"season":20222023,"metric":"goals","is_partial":true,"warning":"Lower-bound totals from single-team player rows only. Multi-team rows contain combined season totals without team splits and are excluded.","excluded_multi_team_players":95,"teams":[{"partial_rank":1,"team_code":"EDM","lower_bound_total":302,"players_included":25},{"partial_rank":2,"team_code":"BOS","lower_bound_total":284,"players_included":29}]}
```

Use `metric=shots` for the corresponding shot ranking; FLA leads with 2,964 known shots.

## Data limitations and assumptions

- The file contains skater aggregates only: no goalies, game dates, transactions, or roster status.
- Multi-team rows contain combined full-season statistics, not a split for each listed team.
- The final team token is treated as an inferred season-end team; its chronology is not independently
  confirmed by the CSV.
- Exact team totals and official league ranks cannot be calculated. The team endpoint returns partial
  lower bounds and never attributes a traded player's combined total to one or every team.
- `S%` and `FOW%` are stored as fractions; structurally unavailable values remain null.

## Tests and verification

Run the complete test suite without installing Python packages on the host:

```bash
docker compose --profile test run --rm --build test
docker compose --profile test run --rm test ruff check --no-cache .
docker compose --profile test run --rm test ruff format --check --no-cache .
```

Observed final checks:

- 28 pytest tests passed across ingestion, transaction behavior, API calculations, caveats, and errors.
- Fresh Compose startup loaded 951 rows with 951 distinct `(player_id, season)` keys.
- Totals matched the source: 8,247 goals, 81,965 shots, and 23,441 penalty minutes.
- A second ingestion still produced 951 rows and the same totals.
- `/health`, every analytical endpoint, and `/openapi.json` returned successfully against PostgreSQL.

## Challenges and tradeoffs

- Duplicate blank CSV headers required validating the raw positional header before pandas renamed them.
- One name contained a control byte, so display text is sanitized while the numeric ID remains canonical.
- Traded-player aggregates make exact team attribution impossible; returning labeled lower bounds is
  more useful and honest than fabricating splits.
- The source field is PIM, so the API says “penalty minutes” rather than claiming penalty counts.
- Transactional season replacement is simple and reconciles removed rows, but a larger system would
  add ingestion-run audit records, checksums, migrations, scheduling, authentication, and observability.

## Time spent

Approximately five focused hours, including data profiling, implementation, automated tests, fresh
Docker/PostgreSQL verification, and documentation.

## AI usage disclosure

OpenAI Codex/ChatGPT was used to inspect the take-home and dataset, compare patterns in related local
projects, research current official framework guidance, propose architecture, draft code and tests,
and review documentation. All generated work was checked against the source CSV and executed locally.

- Accepted: ID-first identity, transactional snapshot replacement, explicit inference/partial-result
  labels, Compose health/dependency sequencing, and focused oracle tests.
- Modified: an initially broader architecture was reduced to one table, one one-shot loader, five
  analyst routes, and no frontend; endpoint names and response fields were made dataset-specific.
- Rejected: assigning a traded player's full totals to every or only the final team, adding an outside
  NHL data source, predictive modeling, AWS/Terraform, Kubernetes, authentication, Alembic, and a UI.
- Reason: these additions either misstate the supplied data or add scope without improving the
  worksheet's required ingestion, database, API, reproducibility, and communication goals.
