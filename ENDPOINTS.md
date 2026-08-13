# API Endpoints Reference

FastAPI service defined in `api/routes.py` (`uvicorn api.routes:create_app --factory`). Backed by
the PostgreSQL schema in `storage/models.py`, populated by `main.py seed|backfill|refresh`.
Season IDs use the NHL `YYYYZZZZ` format (e.g. `20222023`); the configured range is
`backfill_start_season_id` (default `20222023`) through `backfill_through_season_id`
(default `20262027`) via `config.Settings`.

| # | Method & Path | Purpose |
|---|---|---|
| 1 | `GET /health` | Liveness/DB-connectivity check |
| 2 | `GET /players/most-goals` | Top goal scorers for a season |
| 3 | `GET /players/penalties-per-minute` | Penalty-minutes-per-TOI-minute leaders |
| 4 | `GET /players/leaderboard` | Player leaderboard by points, assists, or shooting percentage |
| 5 | `GET /teams/rankings` | Team leaderboard by goals or shots |
| 6 | `GET /standings` | Latest dated standings snapshot for a season |
| 7 | `GET /players/multi-team` | Players who played for >1 team in a season |
| 8 | `GET /rosters/current/{team_abbrev}` | Latest active roster snapshot for a team |
| 9 | `GET /pipeline/status` | Most recent ingestion run's status/metrics |

---

## 1. `GET /health`

No parameters. Returns `503` if the database is unreachable.

**Response**
```json
{ "status": "ok", "database": "reachable" }
```

---

## 2. `GET /players/most-goals`

**Query params:** `season_id` (int, default `20222023`), `limit` (1–100, default `1`)
**Source table:** `player_season_stats` joined to `players`
**Years:** any configured season; 2022-23 is seeded from the supplied CSV, later seasons
require a `backfill`/`refresh` run against NHL Stats REST (`skater/summary`).

**Response columns:** `player_id`, `name`, `goals`, `games_played`

**Real sample** (`?season_id=20222023&limit=3`, from the seeded CSV):
```json
[
  {"player_id": 8478402, "name": "Connor McDavid", "goals": 64, "games_played": 82},
  {"player_id": 8477956, "name": "David Pastrnak", "goals": 61, "games_played": 82},
  {"player_id": 8478420, "name": "Mikko Rantanen", "goals": 55, "games_played": 82}
]
```

---

## 3. `GET /players/penalties-per-minute`

**Query params:** `season_id` (int, default `20222023`), `min_games` (>=0, default `0`), `limit` (1–100, default `10`)
**Source table:** `player_season_stats` (`pim`, `toi_seconds`) joined to `players`
**Important detail:** `toi_seconds` comes from `skater/timeonice` (or the seed CSV's
`SecPerGP * GP`); players with `toi_seconds <= 0` are excluded to avoid a divide-by-zero.

**Response columns:** `player_id`, `name`, `pim`, `total_toi_minutes`, `pim_per_minute`
(sorted by `pim_per_minute` descending)

**Real sample** (`?season_id=20222023&limit=2`):
```json
[
  {"player_id": 8474190, "name": "Wayne Simmonds", "pim": 49, "total_toi_minutes": 134.08, "pim_per_minute": 0.3654},
  {"player_id": 8482157, "name": "Will Cuylle", "pim": 10, "total_toi_minutes": 27.83, "pim_per_minute": 0.3593}
]
```

---

## 4. `GET /teams/rankings`

**Query params:** `season_id` (int, default `20222023`), `metric` (`goals`|`shots`, default `goals`), `limit` (1–32, default `10`)
**Source table:** `team_game_stats` (`goals_for`/`shots_for`, summed per team via `func.sum`)
**Important detail:** requires per-game team rows from `team/summary?isGame=true`, which
only exist after a `backfill`/`refresh` run — **not** populated by the offline seed CSV.
Invalid `metric` values return `400`.

**Response columns:** `team_id`, `team_abbrev` (as `"team"`), and the requested `metric`
value (integer sum)

**Shape** (illustrative — populate via `backfill`):
```json
[
  {"team_id": 10, "team": "TOR", "goals": 297},
  {"team_id": 22, "team": "EDM", "goals": 285}
]
```

---

## 5. `GET /players/multi-team`

**Query params:** `season_id` (int, default `20222023`)
**Source table:** `player_season_stats.team_abbrev` (comma-separated list retained as-is
from the source CSV/API; never used to attribute team-level aggregates)

**Response columns:** `player_id`, `name`, `teams` (sorted unique list), `team_count`,
`team_changes` (`team_count - 1`). Only players with `team_count > 1` are included.

**Real sample:**
```json
[
  {"player_id": 8478569, "name": "Noel Acciari", "teams": ["STL", "TOR"], "team_count": 2, "team_changes": 1},
  {"player_id": 8479315, "name": "Joey Anderson", "teams": ["CHI", "TOR"], "team_count": 2, "team_changes": 1}
]
```

---

## 6. `GET /rosters/current/{team_abbrev}`

**Path param:** `team_abbrev` (case-insensitive, e.g. `TBL`)
**Source table:** `roster_snapshots`, filtered to the max `snapshot_date` and `active=true`
for that team; returns `[]` if no snapshot exists.
**Important detail:** snapshots come from the web `/v1/roster/{team}/current` endpoint via
the daily `refresh`, dated with the run date (today), not a historical date — there is no
offline seed source for this table.

**Response columns:** `player_id`, `team` (abbrev), `position`, `snapshot_date` (ISO date)

**Shape** (illustrative — populate via `refresh`):
```json
[
  {"player_id": 8478519, "team": "TBL", "position": "C", "snapshot_date": "2026-08-13"}
]
```

---

## 7. `GET /pipeline/status`

No parameters. Reports the most recently **started** run (`seed`, `refresh`, or
`refresh-as-of`).

**Important detail:** `backfill` does *not* write a `pipeline_runs` row (only `refresh`
does via `_start_run`/`_finish_run`), so this endpoint reflects incremental-refresh
history, not one-time backfills. Returns `{"status": "never_run"}` before the first refresh.

**Response columns:** `run_id`, `status` (`running`/`succeeded`/`failed`), `command`,
`started_at`, `completed_at`, `seasons`, `row_counts` (per-table counts from the run),
`error` (truncated to 2000 chars)

**Real sample** (before any refresh has run):
```json
{ "status": "never_run" }
```

**Shape after a refresh** (illustrative):
```json
{
  "run_id": "b6e...-...", "status": "succeeded", "command": "refresh",
  "started_at": "2026-08-13T10:17:03+00:00", "completed_at": "2026-08-13T10:17:41+00:00",
  "seasons": [20262027],
  "row_counts": {"games": 4, "player_game_stats": 210, "team_game_stats": 8,
                 "player_season_stats": 900, "team_season_stats": 32,
                 "standings_snapshots": 32, "roster_snapshots": 736},
  "error": null
}
```
