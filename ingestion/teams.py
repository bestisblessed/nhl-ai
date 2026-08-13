"""Team season and game-log ingestion."""

from ._game_impl import TeamIngestor, parse_team_game, parse_team_season, validate_preseason_empty
from utils.http import get_json


def fetch_team_abbreviations(client) -> dict[int, str]:
    """Return the NHL team-ID to canonical tricode mapping."""
    payload = get_json(client, "team", {"limit": -1})
    return {
        int(row["id"]): str(row.get("triCode") or row.get("rawTricode"))
        for row in payload.get("data", [])
        if row.get("id") is not None and (row.get("triCode") or row.get("rawTricode"))
    }

__all__ = [
    "TeamIngestor",
    "fetch_team_abbreviations",
    "parse_team_game",
    "parse_team_season",
    "validate_preseason_empty",
]
