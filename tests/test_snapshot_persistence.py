from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ingestion.records import RosterRecord, ScoreRecord, StandingsRecord
from storage.models import Base, Game, Player, RosterSnapshot, StandingsSnapshot
from storage.persistence import upsert_roster_rows, upsert_score_rows, upsert_standings_rows


def _score(*, home_score: int) -> ScoreRecord:
    return ScoreRecord(
        game_id=2024021307,
        season_id=20242025,
        game_type_id=2,
        game_date="2025-04-17",
        game_state="OFF",
        schedule_state="OK",
        start_time_utc="2025-04-17T23:00:00Z",
        home_team_id=7,
        visiting_team_id=4,
        home_abbrev="BUF",
        visiting_abbrev="PHI",
        home_score=home_score,
        visiting_score=4,
        home_sog=31,
        visiting_sog=24,
    )


def _standing(*, points: int) -> StandingsRecord:
    return StandingsRecord(
        snapshot_date="2025-04-17",
        season_id=20242025,
        game_type_id=2,
        team_id=None,
        team_abbrev="WPG",
        team_name="Winnipeg Jets",
        rank=1,
        conference="Western",
        division="Central",
        games_played=82,
        wins=56,
        losses=22,
        ot_losses=4,
        points=points,
        goals_for=277,
        goals_against=191,
        goal_differential=86,
    )


def _roster(*, sweater_number: int) -> RosterRecord:
    return RosterRecord(
        snapshot_date="2026-08-13",
        team_abbrev="TBL",
        player_id=8478519,
        roster_group="forwards",
        first_name="Anthony",
        last_name="Cirelli",
        sweater_number=sweater_number,
        position_code="C",
        shoots_catches="L",
        birth_date="1997-07-15",
        height_inches=72,
        weight_pounds=191,
        source_season_id=None,
    )


def test_score_upsert_updates_existing_game_without_erasing_schedule_metadata():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Game(
            game_id=2024021307,
            season_id=20242025,
            game_type_id=2,
            game_date=date(2025, 4, 17),
            venue="KeyBank Center",
        ))
        session.commit()

        assert upsert_score_rows(session, [_score(home_score=5)]) == 1
        assert upsert_score_rows(session, [_score(home_score=6)]) == 1
        session.commit()

        game = session.get(Game, 2024021307)
        assert game is not None
        assert (game.home_goals, game.away_goals, game.game_state) == (6, 4, "OFF")
        assert (game.home_team_abbrev, game.away_team_abbrev) == ("BUF", "PHI")
        assert game.venue == "KeyBank Center"
        assert session.query(Game).count() == 1


def test_standings_upsert_resolves_team_id_and_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert upsert_standings_rows(session, [_standing(points=116)], team_ids={"WPG": 52}) == 1
        assert upsert_standings_rows(session, [_standing(points=117)], team_ids={"WPG": 52}) == 1
        session.commit()

        snapshot = session.scalar(select(StandingsSnapshot))
        assert snapshot is not None
        assert (snapshot.team_id, snapshot.points, snapshot.snapshot_date) == (52, 117, date(2025, 4, 17))
        assert session.query(StandingsSnapshot).count() == 1


def test_roster_upsert_creates_player_and_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert upsert_roster_rows(
            session, [_roster(sweater_number=71)], team_ids={"TBL": 14}, season_id=20252026
        ) == 1
        assert upsert_roster_rows(
            session, [_roster(sweater_number=72)], team_ids={"TBL": 14}, season_id=20252026
        ) == 1
        session.commit()

        player = session.get(Player, 8478519)
        snapshot = session.scalar(select(RosterSnapshot))
        assert player is not None and player.full_name == "Anthony Cirelli"
        assert snapshot is not None
        assert (snapshot.team_id, snapshot.season_id, snapshot.sweater_number) == (14, 20252026, 72)
        assert session.query(RosterSnapshot).count() == 1
