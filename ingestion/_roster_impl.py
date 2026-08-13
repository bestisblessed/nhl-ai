"""Ingestion for web API roster snapshots and dated standings."""

from collections.abc import Mapping
from typing import Any

from utils.http import get_json
from .records import RosterRecord, StandingsRecord
from utils.stats import _int


def _default(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("default")
    return value


class RosterIngestor:
    def __init__(self, client: Any):
        self.client = client

    def fetch_current(self, team_abbrev: str, *, snapshot_date: str) -> list[RosterRecord]:
        payload = get_json(self.client, f"/v1/roster/{team_abbrev}/current")
        return parse_roster(payload, team_abbrev=team_abbrev, snapshot_date=snapshot_date)

    def fetch_season(self, team_abbrev: str, season_id: int, *, snapshot_date: str) -> list[RosterRecord]:
        payload = get_json(self.client, f"/v1/roster/{team_abbrev}/{season_id}")
        return parse_roster(
            payload,
            team_abbrev=team_abbrev,
            snapshot_date=snapshot_date,
            source_season_id=season_id,
        )


class StandingsIngestor:
    def __init__(self, client: Any):
        self.client = client

    def fetch_date(self, date: str, *, team_ids: Mapping[str, int] | None = None) -> list[StandingsRecord]:
        payload = get_json(self.client, f"/v1/standings/{date}")
        return [
            parse_standing(row, snapshot_date=date, team_ids=team_ids)
            for row in payload.get("standings", [])
        ]


def parse_roster(
    payload: dict[str, Any],
    *,
    team_abbrev: str,
    snapshot_date: str,
    source_season_id: int | None = None,
) -> list[RosterRecord]:
    records: list[RosterRecord] = []
    for group in ("forwards", "defensemen", "goalies"):
        for player in payload.get(group, []) or []:
            records.append(
                RosterRecord(
                    snapshot_date=snapshot_date,
                    team_abbrev=team_abbrev,
                    player_id=int(player["id"]),
                    roster_group=group,
                    first_name=_default(player.get("firstName")),
                    last_name=_default(player.get("lastName")),
                    sweater_number=_int(player.get("sweaterNumber")),
                    position_code=player.get("positionCode"),
                    shoots_catches=player.get("shootsCatches"),
                    birth_date=player.get("birthDate"),
                    height_inches=_int(player.get("heightInInches")),
                    weight_pounds=_int(player.get("weightInPounds")),
                    source_season_id=source_season_id,
                )
            )
    return records


def parse_standing(
    row: dict[str, Any],
    *,
    snapshot_date: str,
    team_ids: Mapping[str, int] | None = None,
) -> StandingsRecord:
    abbreviation = _default(row.get("teamAbbrev"))
    return StandingsRecord(
        snapshot_date=snapshot_date,
        season_id=_int(row.get("seasonId")),
        game_type_id=_int(row.get("gameTypeId")),
        # The web standings payload currently has teamAbbrev but no numeric id;
        # resolve it against the team dimension during persistence.
        team_id=_int(row.get("teamId", row.get("id")))
        or (team_ids or {}).get(abbreviation or ""),
        team_abbrev=abbreviation,
        team_name=_default(row.get("teamName")),
        conference=row.get("conferenceName") or row.get("conferenceAbbrev"),
        division=row.get("divisionName") or row.get("divisionAbbrev"),
        games_played=_int(row.get("gamesPlayed")),
        wins=_int(row.get("wins")),
        losses=_int(row.get("losses")),
        ot_losses=_int(row.get("otLosses")),
        points=_int(row.get("points")),
        goals_for=_int(row.get("goalFor", row.get("goalsFor"))),
        goals_against=_int(row.get("goalAgainst", row.get("goalsAgainst"))),
        goal_differential=_int(row.get("goalDifferential")),
    )


__all__ = [
    "RosterIngestor",
    "StandingsIngestor",
    "parse_roster",
    "parse_standing",
]
