"""Team season and game-log ingestion."""

from ._game_impl import TeamIngestor, parse_team_game, parse_team_season, validate_preseason_empty

__all__ = ["TeamIngestor", "parse_team_game", "parse_team_season", "validate_preseason_empty"]
