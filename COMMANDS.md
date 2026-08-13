Below is the reproducible command sequence for the `main` branch.

1. Clone/open the repository:

```bash
cd /Users/td/Code/nhl-ai
```

2. Create a local environment file:

```bash
cp .env.example .env
```

Set `DATABASE_URL` in `.env` to a reachable PostgreSQL database before running
any application or CLI command. The application has no SQLite fallback.

For the normal Docker workflow, one command is sufficient on a fresh machine:

```bash
./run_docker_compose.sh start
```

The start command builds and starts FastAPI/PostgreSQL, checks the health
endpoint, and automatically runs the initial backfill plus first incremental
refresh when the 2022-23 seed rows are absent. Existing populated volumes skip
both ingestion steps. Run the daily incremental update separately with:

```bash
./refresh.sh
```

3. Install the project and test dependencies:

```bash
python -m pip install -e '.[api,test]'
```

4. Run syntax compilation:

```bash
PYTHONPYCACHEPREFIX=/tmp/nhl-pyc \
python -m compileall -q ingestion storage utils api config.py main.py tests
```

5. Run the full test suite:

```bash
python -m pytest tests
```

6. Load only the supplied seed CSV into a temporary SQLite test database:

```bash
SEED_CSV_PATH=data/data_dump.csv \
DATABASE_URL=sqlite:////tmp/nhl-ai-test.db \
python main.py backfill --offline-seed-only
```

Expected result:

```text
{"seed": 951}
```

7. Run the seed-only CLI command:

```bash
python main.py seed
```

8. Run the complete historical backfill manually when needed:

```bash
python main.py backfill
```

This loads:

- 2022-23 seed data
- 2023-24 NHL API data
- 2024-25 NHL API data
- 2025-26 NHL API data
- 2026-27 schedule/preseason state

9. Run the daily refresh:

```bash
python main.py refresh
```

This checks D-1 through D-3, extends backward after a missed successful run up
to `DAILY_MAX_RECOVERY_DAYS`, refreshes current-season cumulative skater/team
totals, and stores current standings and roster snapshots. To replay a known
historical window without moving the normal daily recovery checkpoint:

```bash
python main.py refresh --as-of 2026-04-17
```

12. Start the API directly:

```bash
uvicorn api.routes:create_app --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

13. Test the health endpoint:

```bash
curl http://localhost:8000/health
```

14. Test the 2022-23 goal leader endpoint:

```bash
curl "http://localhost:8000/players/most-goals?season_id=20222023"
```

15. Test penalty rate rankings:

```bash
curl "http://localhost:8000/players/penalties-per-minute?season_id=20222023&min_games=10"
```

16. Test team rankings:

```bash
curl "http://localhost:8000/teams/rankings?season_id=20222023&metric=goals"
```

17. Test team shot rankings:

```bash
curl "http://localhost:8000/teams/rankings?season_id=20222023&metric=shots"
```

18. Test multi-team players:

```bash
curl "http://localhost:8000/players/multi-team?season_id=20222023"
```

19. Test the pipeline status endpoint:

```bash
curl http://localhost:8000/pipeline/status
```

20. Build and start Docker Compose with local PostgreSQL:

```bash
docker compose up --build
```

21. Run tests inside the application container:

```bash
docker compose run --rm api python -m pytest
```

22. Stop Docker Compose:

```bash
docker compose down
```

23. Inspect final worktree changes:

```bash
git status --short
git diff --check
```

The take-home uses SQLAlchemy schema creation rather than Alembic migrations.
For a production deployment, add versioned migrations and an external scheduler;
the incremental refresh, player/team game corrections, run status, standings,
and roster snapshots are wired into the current orchestration path.
