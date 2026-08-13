from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.routes import create_app
from config import Settings
from storage.db import create_schema, make_engine
from storage.models import PipelineRun, Player, RosterSnapshot
from ingestion.pipeline import load_seed
from sqlalchemy.orm import Session


def test_seed_to_api_vertical_slice(tmp_path):
    db_path = tmp_path / "nhl.db"
    settings = Settings(seed_csv_path=Path(__file__).parents[1] / "data" / "data_dump.csv", database_url=f"sqlite:///{db_path}")
    assert load_seed(settings) == 951
    client = TestClient(create_app(settings))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "reachable"}
    response = client.get("/players/most-goals", params={"season_id": 20222023})
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Connor McDavid"
    assert response.json()[0]["goals"] == 64


def test_schema_creation_is_repeatable(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'x.db'}")
    engine = make_engine(settings)
    create_schema(engine)
    create_schema(engine)


def test_health_reports_database_failure(tmp_path):
    missing_parent = tmp_path / "missing" / "nhl.db"
    settings = Settings(database_url=f"sqlite:///{missing_parent}")
    response = TestClient(create_app(settings)).get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


def test_current_roster_returns_only_latest_snapshot_and_status_is_diagnostic(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'snapshots.db'}")
    engine = make_engine(settings)
    create_schema(engine)
    with Session(engine) as session:
        session.add(Player(player_id=1, full_name="Test Player", position="C"))
        session.add_all([
            RosterSnapshot(snapshot_date=date(2026, 8, 12), team_id=14, player_id=1,
                           season_id=20262027, team_abbrev="TBL", position="C"),
            RosterSnapshot(snapshot_date=date(2026, 8, 13), team_id=14, player_id=1,
                           season_id=20262027, team_abbrev="TBL", position="C"),
        ])
        session.add(PipelineRun(
            run_id="test-run",
            command="refresh",
            status="failed",
            started_at=datetime(2026, 8, 13, 10, tzinfo=UTC),
            completed_at=datetime(2026, 8, 13, 10, 1, tzinfo=UTC),
            seasons=[20262027],
            error="test failure",
        ))
        session.commit()

    client = TestClient(create_app(settings))
    roster = client.get("/rosters/current/TBL").json()
    assert len(roster) == 1
    assert roster[0]["snapshot_date"] == "2026-08-13"
    status = client.get("/pipeline/status").json()
    assert status["status"] == "failed"
    assert status["seasons"] == [20262027]
    assert status["error"] == "test failure"
