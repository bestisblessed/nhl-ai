"""Ingestion for games, daily scores, and team summary reports."""

from collections.abc import Iterable
from typing import Any

from ._http import get_json
from .records import GameRecord, ScoreRecord, TeamGameRecord, TeamSeasonRecord
from .stats import _float, _int, fetch_report


class GameIngestor:
    def __init__(self, client: Any):
        self.client = client

    def fetch_season(self, season_id: int, game_type_id: int = 2) -> list[GameRecord]:
        rows = fetch_report(
            self.client,
            "game",
            params={
                "cayenneExp": f"season={season_id} and gameType={game_type_id}",
                "sort": [{"property": "id", "direction": "ASC"}],
            },
        )
        return [parse_game(row) for row in rows]


class ScoreIngestor:
    def __init__(self, client: Any):
        self.client = client

    def fetch_date(self, date: str) -> list[ScoreRecord]:
        payload = get_json(self.client, f"/v1/score/{date}")
        return [parse_score(row) for row in payload.get("games", [])]


class TeamIngestor:
    def __init__(self, client: Any):
        self.client = client

    def fetch_games(self, season_id: int, game_type_id: int = 2) -> list[TeamGameRecord]:
        params = {
            "isAggregate": "false",
            "isGame": "true",
            "cayenneExp": f"seasonId={season_id} and gameTypeId={game_type_id}",
            "sort": [{"property": "gameId", "direction": "ASC"}, {"property": "teamId", "direction": "ASC"}],
        }
        return [parse_team_game(row) for row in fetch_report(self.client, "team/summary", params=params)]

    def fetch_season(self, season_id: int, game_type_id: int = 2) -> list[TeamSeasonRecord]:
        params = {
            "isAggregate": "false",
            "isGame": "false",
            "cayenneExp": f"seasonId={season_id} and gameTypeId={game_type_id}",
            "sort": [{"property": "teamId", "direction": "ASC"}],
        }
        return [
            parse_team_season(row, season_id=season_id)
            for row in fetch_report(self.client, "team/summary", params=params)
        ]


def parse_game(row: dict[str, Any]) -> GameRecord:
    return GameRecord(
        game_id=int(row["id"]),
        season_id=int(row["season"]),
        game_type_id=int(row["gameType"]),
        game_date=row.get("gameDate"),
        start_time_local=row.get("easternStartTime"),
        game_number=_int(row.get("gameNumber")),
        schedule_state_id=_int(row.get("gameScheduleStateId")),
        state_id=_int(row.get("gameStateId")),
        home_team_id=int(row["homeTeamId"]),
        visiting_team_id=int(row["visitingTeamId"]),
        home_score=_int(row.get("homeScore")),
        visiting_score=_int(row.get("visitingScore")),
        period=_int(row.get("period")),
    )


def parse_score(row: dict[str, Any]) -> ScoreRecord:
    away, home = row.get("awayTeam") or {}, row.get("homeTeam") or {}
    return ScoreRecord(
        game_id=int(row["id"]),
        season_id=int(row["season"]),
        game_type_id=int(row["gameType"]),
        game_date=row.get("gameDate"),
        game_state=row.get("gameState"),
        schedule_state=row.get("gameScheduleState"),
        start_time_utc=row.get("startTimeUTC"),
        home_team_id=_int(home.get("id")),
        visiting_team_id=_int(away.get("id")),
        home_abbrev=home.get("abbrev"),
        visiting_abbrev=away.get("abbrev"),
        home_score=_int(home.get("score")),
        visiting_score=_int(away.get("score")),
        home_sog=_int(home.get("sog")),
        visiting_sog=_int(away.get("sog")),
    )


def parse_team_game(row: dict[str, Any]) -> TeamGameRecord:
    return TeamGameRecord(
        game_id=int(row["gameId"]),
        team_id=int(row["teamId"]),
        game_date=row.get("gameDate"),
        home_road=row.get("homeRoad"),
        team_abbrev=row.get("teamAbbrev"),
        opponent_team_abbrev=row.get("opponentTeamAbbrev"),
        games_played=_int(row.get("gamesPlayed")),
        goals_for=_int(row.get("goalsFor")),
        goals_against=_int(row.get("goalsAgainst")),
        shots_for_per_game=_float(row.get("shotsForPerGame")),
        shots_against_per_game=_float(row.get("shotsAgainstPerGame")),
        wins=_int(row.get("wins")),
        losses=_int(row.get("losses")),
        ot_losses=_int(row.get("otLosses")),
        points=_int(row.get("points")),
    )


def parse_team_season(row: dict[str, Any], *, season_id: int | None = None) -> TeamSeasonRecord:
    return TeamSeasonRecord(
        season_id=int(row.get("seasonId", season_id)),
        team_id=int(row["teamId"]),
        team_full_name=row.get("teamFullName"),
        games_played=_int(row.get("gamesPlayed")),
        goals_for=_int(row.get("goalsFor")),
        goals_against=_int(row.get("goalsAgainst")),
        shots_for_per_game=_float(row.get("shotsForPerGame")),
        shots_against_per_game=_float(row.get("shotsAgainstPerGame")),
        wins=_int(row.get("wins")),
        losses=_int(row.get("losses")),
        ot_losses=_int(row.get("otLosses")),
        points=_int(row.get("points")),
    )


def validate_preseason_empty(*, season_id: int, final_game_count: int, stat_records: Iterable[Any]) -> None:
    """Allow empty current-season stats only while no regular game is final."""
    count = sum(1 for _ in stat_records)
    if count == 0 and final_game_count > 0:
        raise ValueError(
            f"season {season_id} has {final_game_count} final regular-season games but no statistics"
        )


__all__ = [
    "GameIngestor",
    "ScoreIngestor",
    "TeamIngestor",
    "parse_game",
    "parse_score",
    "parse_team_game",
    "parse_team_season",
    "validate_preseason_empty",
]
