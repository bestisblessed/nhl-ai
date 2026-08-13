from datetime import date

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from storage.db import create_schema
from storage.models import (
    Base,
    Game,
    PipelineRun,
    Player,
    PlayerSeasonStats,
    Season,
)


def test_schema_contains_all_pipeline_tables():
    engine = create_engine("sqlite:///:memory:")
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == {
        "seasons",
        "players",
        "player_season_stats",
        "player_game_stats",
        "games",
        "team_game_stats",
        "team_season_stats",
        "standings_snapshots",
        "roster_snapshots",
        "pipeline_runs",
    }


def test_composite_season_stats_key_is_idempotent_upsert_target():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Season(season_id=20222023, game_type_id=2, state="seeded"))
        session.add(Player(player_id=8470001, full_name="Test Player", position="C"))
        session.add(
            PlayerSeasonStats(
                player_id=8470001,
                season_id=20222023,
                game_type_id=2,
                games_played=1,
                goals=1,
            )
        )
        session.commit()

        row = session.scalar(
            select(PlayerSeasonStats).where(
                PlayerSeasonStats.player_id == 8470001,
                PlayerSeasonStats.season_id == 20222023,
                PlayerSeasonStats.game_type_id == 2,
            )
        )
        assert row is not None
        assert row.goals == 1


def test_game_and_pipeline_run_accept_operational_metadata():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Game(
                game_id=20230001,
                season_id=20222023,
                game_type_id=2,
                game_date=date(2022, 10, 12),
                game_state="OFF",
            )
        )
        session.add(
            PipelineRun(
                command="refresh",
                status="succeeded",
                seasons=[20222023],
                row_counts={"games": 1},
            )
        )
        session.commit()
        assert session.query(Game).count() == 1
        assert session.query(PipelineRun).one().row_counts == {"games": 1}
