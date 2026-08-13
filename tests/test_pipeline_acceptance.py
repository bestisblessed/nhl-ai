from pathlib import Path

from fastapi.testclient import TestClient

from api.routes import create_app
from config import Settings
from storage.db import create_schema, make_engine
from storage.models import Player, PlayerSeasonStats
from ingestion.pipeline import load_seed
from sqlalchemy.orm import Session


def test_seed_to_api_vertical_slice(tmp_path):
    db_path = tmp_path / "nhl.db"
    settings = Settings(seed_csv_path=Path(__file__).parents[1] / "data" / "data_dump.csv", database_url=f"sqlite:///{db_path}")
    assert load_seed(settings) == 951
    client = TestClient(create_app(settings))
    response = client.get("/players/most-goals", params={"season_id": 20222023})
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Connor McDavid"
    assert response.json()[0]["goals"] == 64


def test_schema_creation_is_repeatable(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'x.db'}")
    engine = make_engine(settings)
    create_schema(engine)
    create_schema(engine)
