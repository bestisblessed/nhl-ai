"""Small transactional writers shared by the CLI and API."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from sqlalchemy.orm import Session

from .models import (
    Game,
    Player,
    PlayerGameStats,
    PlayerSeasonStats,
    RosterSnapshot,
    StandingsSnapshot,
    TeamGameStats,
    TeamSeasonStats,
)
from ingestion.records import (
    GameRecord,
    PlayerGameRecord,
    RosterRecord,
    ScoreRecord,
    StandingsRecord,
    TeamGameRecord,
    TeamSeasonRecord,
)
from ingestion.seed import SeedSkaterRow
from ingestion.skaters import SkaterSeasonRow


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
        if row.game_date is None:
            raise ValueError(f"game record {row.game_id} is missing game_date")
        session.merge(Game(
            game_id=row.game_id, season_id=row.season_id, game_type_id=row.game_type_id,
            game_date=date.fromisoformat(row.game_date), start_time_utc=_datetime(row.start_time_local),
            away_team_id=row.visiting_team_id, home_team_id=row.home_team_id,
            away_goals=row.visiting_score, home_goals=row.home_score,
        ))
        count += 1
    return count


def upsert_score_rows(session: Session, rows: Iterable[ScoreRecord]) -> int:
    """Apply the mutable daily-score fields without erasing schedule metadata."""

    count = 0
    source_updated_at = datetime.now(UTC)
    for row in rows:
        game = session.get(Game, row.game_id)
        if game is None:
            if row.game_date is None:
                raise ValueError(f"score record {row.game_id} is missing game_date")
            game = Game(
                game_id=row.game_id,
                season_id=row.season_id,
                game_type_id=row.game_type_id,
                game_date=date.fromisoformat(row.game_date),
            )
            session.add(game)
        elif row.game_date is not None:
            game.game_date = date.fromisoformat(row.game_date)

        game.season_id = row.season_id
        game.game_type_id = row.game_type_id
        game.start_time_utc = _datetime(row.start_time_utc) or game.start_time_utc
        game.away_team_id = row.visiting_team_id or game.away_team_id
        game.away_team_abbrev = row.visiting_abbrev or game.away_team_abbrev
        game.home_team_id = row.home_team_id or game.home_team_id
        game.home_team_abbrev = row.home_abbrev or game.home_team_abbrev
        game.game_state = row.game_state or game.game_state
        game.away_goals = row.visiting_score if row.visiting_score is not None else game.away_goals
        game.home_goals = row.home_score if row.home_score is not None else game.home_goals
        game.source_updated_at = source_updated_at
        count += 1
    return count


def upsert_player_game_rows(session: Session, rows: Iterable[PlayerGameRecord]) -> int:
    """Upsert one row per player, team, and game from Stats REST."""

    count = 0
    for row in rows:
        player = session.get(Player, row.player_id)
        if player is None:
            session.add(Player(
                player_id=row.player_id,
                full_name=row.player_name or f"Unknown Player {row.player_id}",
                position=row.position_code,
            ))
        else:
            if row.player_name:
                player.full_name = row.player_name
            if row.position_code:
                player.position = row.position_code
        session.merge(PlayerGameStats(
            game_id=row.game_id,
            player_id=row.player_id,
            team_id=row.team_id,
            game_type_id=row.game_type_id,
            team_abbrev=row.team_abbrev,
            goals=row.goals,
            assists=row.assists,
            points=row.points,
            pim=row.pim,
            shots=row.shots,
            toi_seconds=row.toi_seconds,
        ))
        count += 1
    return count


def upsert_standings_rows(
    session: Session,
    rows: Iterable[StandingsRecord],
    *,
    team_ids: dict[str, int] | None = None,
) -> int:
    """Upsert a dated standings snapshot, resolving numeric team ids if needed."""

    count = 0
    for row in rows:
        team_id = row.team_id or (team_ids or {}).get(row.team_abbrev or "")
        if team_id is None:
            raise ValueError(f"standings record has no team id for {row.team_abbrev!r}")
        if row.season_id is None or row.game_type_id is None:
            raise ValueError(f"standings record for {row.team_abbrev!r} has no season/game type")
        session.merge(StandingsSnapshot(
            season_id=row.season_id,
            game_type_id=row.game_type_id,
            snapshot_date=date.fromisoformat(row.snapshot_date),
            team_id=team_id,
            team_abbrev=row.team_abbrev,
            rank=row.rank,
            games_played=row.games_played,
            wins=row.wins,
            losses=row.losses,
            overtime_losses=row.ot_losses,
            points=row.points,
            goals_for=row.goals_for,
            goals_against=row.goals_against,
        ))
        count += 1
    return count


def upsert_roster_rows(
    session: Session,
    rows: Iterable[RosterRecord],
    *,
    team_ids: dict[str, int],
    season_id: int | None = None,
) -> int:
    """Upsert current-roster players and their dated team snapshots."""

    count = 0
    for row in rows:
        team_id = team_ids.get(row.team_abbrev)
        if team_id is None:
            raise ValueError(f"roster record has no team id for {row.team_abbrev!r}")

        full_name = " ".join(value for value in (row.first_name, row.last_name) if value)
        player = session.get(Player, row.player_id)
        if player is None:
            player = Player(
                player_id=row.player_id,
                full_name=full_name or f"Unknown Player {row.player_id}",
                position=row.position_code,
                shoots_catches=row.shoots_catches,
            )
            session.add(player)
        else:
            if full_name:
                player.full_name = full_name
            if row.position_code:
                player.position = row.position_code
            if row.shoots_catches:
                player.shoots_catches = row.shoots_catches
            player.active = True

        session.merge(RosterSnapshot(
            snapshot_date=date.fromisoformat(row.snapshot_date),
            team_id=team_id,
            player_id=row.player_id,
            season_id=row.source_season_id or season_id,
            team_abbrev=row.team_abbrev,
            position=row.position_code,
            sweater_number=row.sweater_number,
            roster_type=row.roster_group,
            active=True,
        ))
        count += 1
    return count


def upsert_team_rows(
    session: Session,
    rows: Iterable[TeamGameRecord],
    *,
    season_id: int,
    team_abbrevs: dict[int, str],
    game_type_id: int = 2,
) -> int:
    count = 0
    team_ids = {abbrev: team_id for team_id, abbrev in team_abbrevs.items()}
    for row in rows:
        session.merge(TeamGameStats(
            game_id=row.game_id, team_id=row.team_id, season_id=season_id, game_type_id=game_type_id,
            team_abbrev=team_abbrevs[row.team_id],
            opponent_team_id=team_ids.get(row.opponent_team_abbrev or ""),
            opponent_team_abbrev=row.opponent_team_abbrev,
            home_away=row.home_road, goals_for=row.goals_for or 0, goals_against=row.goals_against or 0,
            shots_for=round(row.shots_for_per_game or 0), shots_against=round(row.shots_against_per_game or 0),
            wins=row.wins or 0, losses=row.losses or 0, overtime_losses=row.ot_losses or 0,
            points=row.points or 0,
        ))
        count += 1
    return count


def upsert_team_season_rows(
    session: Session,
    rows: Iterable[TeamSeasonRecord],
    *,
    team_abbrevs: dict[int, str],
    game_type_id: int = 2,
) -> int:
    count = 0
    for row in rows:
        session.merge(TeamSeasonStats(
            season_id=row.season_id, team_id=row.team_id, game_type_id=game_type_id,
            team_abbrev=team_abbrevs[row.team_id], games_played=row.games_played or 0,
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
