Below is the reproducible command sequence for the implementation.

1. Clone/open the repository:

```bash
cd /Users/td/Code/nhl-ai
```

2. Create the implementation worktree:

```bash
git worktree add -b nhl-ai-initial-scraper-plan \
  /Users/td/Code/nhl-ai-initial-scraper-plan main
```

3. Enter the worktree:

```bash
cd /Users/td/Code/nhl-ai-initial-scraper-plan
```

4. Create a local environment file:

```bash
cp .env.example .env
```

5. Install the project and test dependencies:

```bash
python -m pip install -e '.[api,test]'
```

6. Run syntax compilation:

```bash
PYTHONPYCACHEPREFIX=/tmp/nhl-pyc \
python -m compileall -q ingestion storage utils api config.py main.py tests
```

7. Run the full test suite:

```bash
python -m pytest tests
```

8. Load only the supplied seed CSV into SQLite:

```bash
SEED_CSV_PATH=data/data_dump.csv \
DATABASE_URL=sqlite:////tmp/nhl-ai-test.db \
python main.py backfill --offline-seed-only
```

Expected result:

```text
{"seed": 951}
```

9. Run the seed-only CLI command:

```bash
python main.py seed
```

10. Run the complete historical backfill:

```bash
python main.py backfill
```

This loads:

- 2022-23 seed data
- 2023-24 NHL API data
- 2024-25 NHL API data
- 2025-26 NHL API data
- 2026-27 schedule/preseason state

11. Run the daily refresh:

```bash
python main.py refresh
```

12. Start the API directly:

```bash
uvicorn api.routes:app \
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

20. Build and start Docker Compose:

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

The implementation did not create Alembic migrations or persist roster/standings records through the main orchestration path yet, so those pieces would need to be completed before treating Docker/PostgreSQL as production-ready.
