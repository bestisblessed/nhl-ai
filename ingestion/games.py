"""Game schedule and daily score ingestion."""

from ._game_impl import GameIngestor, ScoreIngestor, parse_game, parse_score

__all__ = ["GameIngestor", "ScoreIngestor", "parse_game", "parse_score"]
