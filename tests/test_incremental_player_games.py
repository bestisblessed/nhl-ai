from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from ingestion.records import PlayerGameRecord
from ingestion.skaters import SkaterStatsIngestor
from storage.models import Base, Game, Player, PlayerGameStats
from storage.persistence import upsert_player_game_rows


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_json(self, path, params):
        self.calls.append((path, params))
        return self.payload, None


def _api_row(**changes):
    row = {
        "gameId": 2025021307,
        "playerId": 8474564,
        "skaterFullName": "Steven Stamkos",
        "teamAbbrev": "NSH",
        "positionCode": "C",
        "goals": 2,
        "assists": 1,
        "points": 3,
        "penaltyMinutes": 0,
        "shots": 3,
        "timeOnIcePerGame": 1009.0,
    }
    row.update(changes)
    return row


def test_date_scoped_fetch_and_normalization():
    fake = FakeClient({"data": [_api_row()], "total": 1})
    ingestor = SkaterStatsIngestor(fake)

    raw = ingestor.fetch_game_summary(20252026, game_date="2026-04-16")
    rows = ingestor.normalize_games(raw, team_ids_by_abbrev={"NSH": 18})

    assert fake.calls[0][0] == "skater/summary"
    assert fake.calls[0][1]["isGame"] == "true"
    assert fake.calls[0][1]["cayenneExp"] == (
        'seasonId=20252026 and gameTypeId=2 and gameDate="2026-04-16"'
    )
    assert rows == [PlayerGameRecord(
        game_id=2025021307,
        player_id=8474564,
        player_name="Steven Stamkos",
        team_id=18,
        team_abbrev="NSH",
        position_code="C",
        game_type_id=2,
        goals=2,
        assists=1,
        points=3,
        pim=0,
        shots=3,
        toi_seconds=1009.0,
    )]


def test_normalization_rejects_unknown_team_abbreviation():
    with pytest.raises(ValueError, match="unknown team abbreviation"):
        SkaterStatsIngestor(FakeClient({})).normalize_games(
            [_api_row(teamAbbrev="XXX")],
            team_ids_by_abbrev={"NSH": 18},
        )


def test_player_game_upsert_is_idempotent():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    row = PlayerGameRecord(
        game_id=2025021307,
        player_id=8474564,
        player_name="Steven Stamkos",
        team_id=18,
        team_abbrev="NSH",
        position_code="C",
        game_type_id=2,
        goals=2,
        assists=1,
        points=3,
        pim=0,
        shots=3,
        toi_seconds=1009.0,
    )

    with Session(engine) as session:
        session.add(Game(
            game_id=row.game_id,
            season_id=20252026,
            game_type_id=2,
            game_date=date(2026, 4, 16),
        ))
        session.add(Player(
            player_id=row.player_id,
            full_name="Old Name",
            position="C",
            shoots_catches="R",
        ))
        session.commit()

        assert upsert_player_game_rows(session, [row]) == 1
        session.commit()
        updated = PlayerGameRecord(**{**row.as_dict(), "goals": 3, "points": 4})
        assert upsert_player_game_rows(session, [updated]) == 1
        session.commit()

        assert session.scalar(select(func.count()).select_from(PlayerGameStats)) == 1
        saved = session.get(PlayerGameStats, (row.game_id, row.player_id, row.team_id))
        assert saved is not None and saved.goals == 3 and saved.points == 4
        player = session.get(Player, row.player_id)
        assert player is not None and player.full_name == "Steven Stamkos"
        assert player.shoots_catches == "R"
