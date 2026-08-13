"""Small transactional writers shared by the CLI and API."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Game, Player, PlayerSeasonStats, Season, TeamGameStats, TeamSeasonStats
from .records import GameRecord, TeamGameRecord, TeamSeasonRecord
from .seed import SeedSkaterRow
from .skaters import SkaterSeasonRow


def upsert_seed(session: Session, rows: Iterable[SeedSkaterRow], *, game_type_id: int = 2) -> int:
    count = 0
    for row in rows:
        session.merge(Player(player_id=row.player_id, full_name=row.name, position=row.position))
        session.merge(PlayerSeasonStats(
            player_id=row.player_id, season_id=row.season_id, game_type_id=game_type_id,
            team_abbrev=row.team, games_played=row.games_played, goals=row.goals,
            assists=row.assists, points=row.points, plus_minus=row.plus_minus, pim=row.pim,
            ppg=row.ppg, shg=row.shg, gwg=row.gwg, shots=row.shots, shooting_pct=row.shooting_pct,
            toi_seconds=(row.seconds_per_game * row.games_played) if row.seconds_per_game is not None else None,
            shifts_per_game=row.shifts_per_game, faceoff_pct=row.faceoff_pct, ppp=row.ppp, shp=row.shp,
        ))
        count += 1
    return count


def upsert_skater_rows(session: Session, rows: Iterable[SkaterSeasonRow], *, game_type_id: int = 2) -> int:
    count = 0
    for row in rows:
        session.merge(Player(player_id=row.player_id, full_name=row.name, position=row.position))
        session.merge(PlayerSeasonStats(
            player_id=row.player_id, season_id=row.season_id, game_type_id=game_type_id,
            team_abbrev=row.team, games_played=row.games_played, goals=row.goals,
            assists=row.assists, points=row.points, plus_minus=row.plus_minus, pim=row.pim,
            ppg=row.ppg, shg=row.shg, gwg=row.gwg, shots=row.shots, shooting_pct=row.shooting_pct,
            toi_seconds=(row.seconds_per_game * row.games_played) if row.seconds_per_game is not None else None,
            shifts_per_game=row.shifts_per_game, faceoff_pct=row.faceoff_pct, ppp=row.ppp, shp=row.shp,
        ))
        count += 1
    return count


def upsert_games(session: Session, rows: Iterable[GameRecord]) -> int:
    count = 0
    for row in rows:
        session.merge(Game(
            game_id=row.game_id, season_id=row.season_id, game_type_id=row.game_type_id,
            game_date=date.fromisoformat(row.game_date), start_time_utc=_datetime(row.start_time_utc),
            away_team_id=row.visiting_team_id, home_team_id=row.home_team_id,
            away_goals=row.visiting_score, home_goals=row.home_score,
        ))
        count += 1
    return count


def upsert_team_rows(session: Session, rows: Iterable[TeamGameRecord], *, season_id: int, game_type_id: int = 2) -> int:
    count = 0
    for row in rows:
        session.merge(TeamGameStats(
            game_id=row.game_id, team_id=row.team_id, season_id=season_id, game_type_id=game_type_id,
            team_abbrev=row.team_abbrev or "UNK", opponent_team_abbrev=row.opponent_team_abbrev,
            home_away=row.home_road, goals_for=row.goals_for or 0, goals_against=row.goals_against or 0,
            shots_for=round(row.shots_for_per_game or 0), shots_against=round(row.shots_against_per_game or 0),
            wins=row.wins or 0, losses=row.losses or 0, overtime_losses=row.ot_losses or 0,
            points=row.points or 0,
        ))
        count += 1
    return count


def upsert_team_season_rows(session: Session, rows: Iterable[TeamSeasonRecord], *, game_type_id: int = 2) -> int:
    count = 0
    for row in rows:
        session.merge(TeamSeasonStats(
            season_id=row.season_id, team_id=row.team_id, game_type_id=game_type_id,
            team_abbrev=row.team_full_name or "UNK", games_played=row.games_played or 0,
            goals_for=row.goals_for or 0, goals_against=row.goals_against or 0,
            shots_for=round((row.shots_for_per_game or 0) * (row.games_played or 0)),
            wins=row.wins or 0, losses=row.losses or 0, overtime_losses=row.ot_losses or 0,
            points=row.points or 0,
        ))
        count += 1
    return count


def _datetime(value: str | None):
    if not value:
        return None
    from datetime import datetime
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
