from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlayerSeasonStats(Base):
    __tablename__ = "player_season_stats"
    __table_args__ = (
        CheckConstraint("games_played > 0", name="ck_games_played_positive"),
        CheckConstraint("goals >= 0 AND assists >= 0", name="ck_scoring_nonnegative"),
        CheckConstraint("points = goals + assists", name="ck_points_identity"),
        CheckConstraint("penalty_minutes >= 0 AND shots >= 0", name="ck_counts_nonnegative"),
        CheckConstraint(
            "shooting_pct IS NULL OR (shooting_pct >= 0 AND shooting_pct <= 1)",
            name="ck_shooting_pct_bounds",
        ),
        CheckConstraint(
            "faceoff_pct IS NULL OR (faceoff_pct >= 0 AND faceoff_pct <= 1)",
            name="ck_faceoff_pct_bounds",
        ),
        CheckConstraint("team_count >= 1", name="ck_team_count_positive"),
    )

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    team_codes: Mapped[str] = mapped_column(String(31))
    final_team: Mapped[str] = mapped_column(String(3), index=True)
    team_count: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(1), index=True)
    games_played: Mapped[int] = mapped_column(Integer)
    goals: Mapped[int] = mapped_column(Integer, index=True)
    assists: Mapped[int] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer)
    plus_minus: Mapped[int] = mapped_column(Integer)
    penalty_minutes: Mapped[int] = mapped_column(Integer)
    power_play_goals: Mapped[int] = mapped_column(Integer)
    short_handed_goals: Mapped[int] = mapped_column(Integer)
    game_winning_goals: Mapped[int] = mapped_column(Integer)
    shots: Mapped[int] = mapped_column(Integer)
    shooting_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    seconds_per_game: Mapped[float] = mapped_column(Float)
    faceoff_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_play_points: Mapped[int] = mapped_column(Integer)
    short_handed_points: Mapped[int] = mapped_column(Integer)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
