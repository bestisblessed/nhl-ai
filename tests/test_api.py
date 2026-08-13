from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from nhl_api.database import get_session
from nhl_api.ingestion import load_and_clean, replace_snapshot
from nhl_api.main import app
from nhl_api.models import Base

DATA_PATH = Path(__file__).parents[1] / "data" / "data_dump.csv"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        replace_snapshot(load_and_clean(DATA_PATH), session)

    def test_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_health_reports_loaded_snapshot(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["rows_loaded"] == 951


def test_goals_leaderboard_and_tie_ranking(client: TestClient) -> None:
    response = client.get("/players/goals-leaders")

    assert response.status_code == 200
    leaders = response.json()
    assert leaders[0] == {
        "rank": 1,
        "player_id": 8478402,
        "name": "Connor McDavid",
        "team_codes": ["EDM"],
        "position": "C",
        "games_played": 82,
        "goals": 64,
    }
    assert [(row["name"], row["goals"], row["rank"]) for row in leaders[-2:]] == [
        ("Nathan MacKinnon", 42, 9),
        ("Alex Ovechkin", 42, 9),
    ]


def test_goals_filters_are_applied(client: TestClient) -> None:
    response = client.get("/players/goals-leaders?limit=1&min_games=83")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["games_played"] >= 83


def test_penalty_rate_leader_uses_ice_time_and_minimum_games(client: TestClient) -> None:
    response = client.get("/players/penalty-rate-leaders?limit=1&min_games=10")

    assert response.status_code == 200
    leader = response.json()[0]
    assert leader["name"] == "Wayne Simmonds"
    assert leader["penalty_minutes"] == 49
    assert leader["total_ice_minutes"] == pytest.approx(134.083, abs=0.001)
    assert leader["penalty_minutes_per_minute"] == pytest.approx(0.365444, abs=0.000001)


def test_team_change_leaders_preserve_source_sequence(client: TestClient) -> None:
    response = client.get("/players/team-changes?limit=2")

    assert response.status_code == 200
    leaders = response.json()
    assert {row["name"] for row in leaders} == {"Dryden Hunt", "Michael Eyssimont"}
    assert all(row["rank"] == 1 for row in leaders)
    assert all(row["team_count"] == 3 and row["team_changes"] == 2 for row in leaders)
    assert next(row for row in leaders if row["name"] == "Michael Eyssimont")["team_codes"] == [
        "WPG",
        "SJS",
        "TBL",
    ]


def test_tampa_bay_roster_is_explicitly_inferred(client: TestClient) -> None:
    response = client.get("/teams/TBL/roster")

    assert response.status_code == 200
    roster = response.json()
    assert roster["is_inferred"] is True
    assert roster["player_count"] == 26
    names = {player["name"] for player in roster["players"]}
    assert {"Michael Eyssimont", "Tanner Jeannot", "Rudolfs Balcers"} <= names
    assert {"Cal Foote", "Vladislav Namestnikov"}.isdisjoint(names)


@pytest.mark.parametrize(
    ("metric", "team", "total"),
    [("goals", "EDM", 302), ("shots", "FLA", 2964)],
)
def test_team_rankings_are_partial_lower_bounds(
    client: TestClient, metric: str, team: str, total: int
) -> None:
    response = client.get(f"/teams/rankings?metric={metric}")

    assert response.status_code == 200
    rankings = response.json()
    assert rankings["is_partial"] is True
    assert rankings["excluded_multi_team_players"] == 95
    assert rankings["teams"][0]["team_code"] == team
    assert rankings["teams"][0]["lower_bound_total"] == total


@pytest.mark.parametrize(
    "path",
    [
        "/players/goals-leaders?limit=0",
        "/players/penalty-rate-leaders?min_games=0",
        "/teams/rankings?metric=points",
        "/teams/tbl/roster",
    ],
)
def test_invalid_parameters_return_422(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/players/goals-leaders?season=19001901",
        "/teams/ZZZ/roster",
        "/teams/TBL/roster?season=19001901",
        "/teams/rankings?season=19001901",
    ],
)
def test_unknown_data_returns_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404
