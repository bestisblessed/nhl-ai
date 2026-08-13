"""Normalized persistence schema for the NHL pipeline."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Float,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class Season(TimestampMixin, Base):
    __tablename__ = "seasons"

    season_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_type_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=2)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="discovered")
    regular_season_start: Mapped[date | None] = mapped_column(Date)
    regular_season_end: Mapped[date | None] = mapped_column(Date)
    expected_games: Mapped[int | None] = mapped_column(Integer)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Player(TimestampMixin, Base):
    __tablename__ = "players"

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[str | None] = mapped_column(String(8))
    shoots_catches: Mapped[str | None] = mapped_column(String(8))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PlayerSeasonStats(Base):
    __tablename__ = "player_season_stats"
    __table_args__ = (Index("ix_player_season_stats_season", "season_id", "game_type_id"),)

    player_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), primary_key=True)
    season_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_abbrev: Mapped[str | None] = mapped_column(String(64))
    games_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plus_minus: Mapped[int | None] = mapped_column(Integer)
    pim: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ppg: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shg: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gwg: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shooting_pct: Mapped[float | None] = mapped_column(Float)
    toi_seconds: Mapped[float | None] = mapped_column(Float)
    shifts_per_game: Mapped[float | None] = mapped_column(Float)
    faceoff_pct: Mapped[float | None] = mapped_column(Float)
    ppp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (Index("ix_games_season_date", "season_id", "game_date"),)

    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    game_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    game_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    away_team_id: Mapped[int | None] = mapped_column(Integer)
    away_team_abbrev: Mapped[str | None] = mapped_column(String(8))
    home_team_id: Mapped[int | None] = mapped_column(Integer)
    home_team_abbrev: Mapped[str | None] = mapped_column(String(8))
    game_state: Mapped[str | None] = mapped_column(String(32))
    venue: Mapped[str | None] = mapped_column(String(160))
    away_goals: Mapped[int | None] = mapped_column(Integer)
    home_goals: Mapped[int | None] = mapped_column(Integer)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"
    __table_args__ = (Index("ix_player_game_stats_game", "game_id"),)

    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    team_abbrev: Mapped[str | None] = mapped_column(String(8))
    goals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pim: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    toi_seconds: Mapped[float | None] = mapped_column(Float)


class TeamGameStats(Base):
    __tablename__ = "team_game_stats"
    __table_args__ = (Index("ix_team_game_stats_season", "season_id"),)

    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    game_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    team_abbrev: Mapped[str] = mapped_column(String(8), nullable=False)
    opponent_team_id: Mapped[int | None] = mapped_column(Integer)
    opponent_team_abbrev: Mapped[str | None] = mapped_column(String(8))
    home_away: Mapped[str | None] = mapped_column(String(4))
    goals_for: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots_for: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots_against: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overtime_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TeamSeasonStats(Base):
    __tablename__ = "team_season_stats"

    season_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_abbrev: Mapped[str] = mapped_column(String(8), nullable=False)
    games_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots_for: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overtime_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank: Mapped[int | None] = mapped_column(Integer)


class StandingsSnapshot(Base):
    __tablename__ = "standings_snapshots"
    __table_args__ = (Index("ix_standings_snapshots_season_date", "season_id", "snapshot_date"),)

    season_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_abbrev: Mapped[str | None] = mapped_column(String(8))
    rank: Mapped[int | None] = mapped_column(Integer)
    games_played: Mapped[int | None] = mapped_column(Integer)
    wins: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)
    overtime_losses: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[int | None] = mapped_column(Integer)
    goals_for: Mapped[int | None] = mapped_column(Integer)
    goals_against: Mapped[int | None] = mapped_column(Integer)


class RosterSnapshot(Base):
    __tablename__ = "roster_snapshots"
    __table_args__ = (Index("ix_roster_snapshots_team_date", "team_id", "snapshot_date"),)

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), primary_key=True)
    season_id: Mapped[int | None] = mapped_column(Integer)
    team_abbrev: Mapped[str | None] = mapped_column(String(8))
    position: Mapped[str | None] = mapped_column(String(8))
    sweater_number: Mapped[int | None] = mapped_column(Integer)
    roster_type: Mapped[str | None] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    command: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seasons: Mapped[list[int] | None] = mapped_column(JSON)
    row_counts: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(2000))
