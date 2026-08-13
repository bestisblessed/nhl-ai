"""Focused FastAPI read surface for the take-home questions."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import Settings
from storage.db import make_engine
from storage.models import (
    Player,
    PlayerSeasonStats,
    PipelineRun,
    RosterSnapshot,
    StandingsSnapshot,
    TeamGameStats,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()
    engine = None
    def get_engine():
        nonlocal engine
        if engine is None:
            engine = make_engine(cfg)
        return engine
    app = FastAPI(title="NHL Take-Home API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"status": "ok", "database": "reachable"}

    @app.get("/players/most-goals")
    def most_goals(season_id: int = Query(20222023), limit: int = Query(1, ge=1, le=100)):
        with Session(get_engine()) as session:
            rows = session.execute(
                select(PlayerSeasonStats, Player).join(Player, Player.player_id == PlayerSeasonStats.player_id)
                .where(PlayerSeasonStats.season_id == season_id)
                .order_by(PlayerSeasonStats.goals.desc(), Player.player_id.asc()).limit(limit)
            ).all()
            return [{"player_id": s.player_id, "name": p.full_name, "goals": s.goals, "games_played": s.games_played} for s, p in rows]

    @app.get("/players/penalties-per-minute")
    def penalties_per_minute(season_id: int = Query(20222023), min_games: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
        with Session(get_engine()) as session:
            rows = session.execute(select(PlayerSeasonStats, Player).join(Player).where(
                PlayerSeasonStats.season_id == season_id, PlayerSeasonStats.games_played >= min_games
            )).all()
            output = []
            for stats, player in rows:
                toi_minutes = (stats.toi_seconds or 0) / 60
                if toi_minutes <= 0:
                    continue
                output.append({"player_id": stats.player_id, "name": player.full_name, "pim": stats.pim,
                               "total_toi_minutes": toi_minutes, "pim_per_minute": stats.pim / toi_minutes})
            return sorted(output, key=lambda row: (-row["pim_per_minute"], row["player_id"]))[:limit]

    @app.get("/players/leaderboard")
    def player_leaderboard(
        season_id: int = Query(20222023),
        metric: str = Query("points"),
        min_games: int = Query(0, ge=0),
        limit: int = Query(10, ge=1, le=100),
    ):
        if metric not in {"points", "assists", "shooting_pct"}:
            raise HTTPException(400, "metric must be points, assists, or shooting_pct")
        column = getattr(PlayerSeasonStats, metric)
        with Session(get_engine()) as session:
            rows = session.execute(
                select(PlayerSeasonStats, Player)
                .join(Player, Player.player_id == PlayerSeasonStats.player_id)
                .where(
                    PlayerSeasonStats.season_id == season_id,
                    PlayerSeasonStats.games_played >= min_games,
                    column.is_not(None),
                )
                .order_by(column.desc(), PlayerSeasonStats.player_id.asc())
                .limit(limit)
            ).all()
            return [
                {
                    "player_id": stats.player_id,
                    "name": player.full_name,
                    "season_id": season_id,
                    "games_played": stats.games_played,
                    metric: getattr(stats, metric),
                }
                for stats, player in rows
            ]

    @app.get("/teams/rankings")
    def team_rankings(season_id: int = Query(20222023), metric: str = Query("goals"), limit: int = Query(10, ge=1, le=32)):
        if metric not in {"goals", "shots"}:
            raise HTTPException(400, "metric must be goals or shots")
        column = TeamGameStats.goals_for if metric == "goals" else TeamGameStats.shots_for
        with Session(get_engine()) as session:
            rows = session.execute(select(TeamGameStats.team_id, TeamGameStats.team_abbrev, func.sum(column).label("value"))
                .where(TeamGameStats.season_id == season_id).group_by(TeamGameStats.team_id, TeamGameStats.team_abbrev)
                .order_by(func.sum(column).desc()).limit(limit)).all()
            return [{"team_id": team_id, "team": team, metric: int(value or 0)} for team_id, team, value in rows]

    @app.get("/standings")
    def standings(season_id: int = Query(20222023)):
        with Session(get_engine()) as session:
            latest_date = session.scalar(
                select(func.max(StandingsSnapshot.snapshot_date)).where(
                    StandingsSnapshot.season_id == season_id
                )
            )
            if latest_date is None:
                return []
            rows = session.execute(
                select(StandingsSnapshot)
                .where(
                    StandingsSnapshot.season_id == season_id,
                    StandingsSnapshot.snapshot_date == latest_date,
                )
                .order_by(StandingsSnapshot.rank.asc(), StandingsSnapshot.team_abbrev.asc())
            ).scalars().all()
            return [
                {
                    "season_id": row.season_id,
                    "snapshot_date": row.snapshot_date.isoformat(),
                    "rank": row.rank,
                    "team_id": row.team_id,
                    "team": row.team_abbrev,
                    "games_played": row.games_played,
                    "wins": row.wins,
                    "losses": row.losses,
                    "overtime_losses": row.overtime_losses,
                    "points": row.points,
                    "goals_for": row.goals_for,
                    "goals_against": row.goals_against,
                }
                for row in rows
            ]

    @app.get("/players/multi-team")
    def multi_team(season_id: int = Query(20222023)):
        with Session(get_engine()) as session:
            rows = session.execute(select(Player, PlayerSeasonStats).join(PlayerSeasonStats).where(PlayerSeasonStats.season_id == season_id)).all()
            output = []
            for player, stats in rows:
                teams = sorted({part.strip() for part in (stats.team_abbrev or "").split(",") if part.strip()})
                if len(teams) > 1:
                    output.append({"player_id": player.player_id, "name": player.full_name, "teams": teams, "team_count": len(teams), "team_changes": len(teams) - 1})
            return output

    @app.get("/rosters/current/{team_abbrev}")
    def current_roster(team_abbrev: str):
        with Session(get_engine()) as session:
            latest_date = session.scalar(
                select(func.max(RosterSnapshot.snapshot_date)).where(
                    RosterSnapshot.team_abbrev == team_abbrev.upper(),
                    RosterSnapshot.active.is_(True),
                )
            )
            if latest_date is None:
                return []
            rows = session.execute(select(RosterSnapshot).where(
                RosterSnapshot.team_abbrev == team_abbrev.upper(),
                RosterSnapshot.snapshot_date == latest_date,
                RosterSnapshot.active.is_(True),
            ).order_by(RosterSnapshot.player_id.asc())).scalars().all()
            return [{"player_id": row.player_id, "team": row.team_abbrev, "position": row.position, "snapshot_date": row.snapshot_date.isoformat()} for row in rows]

    @app.get("/pipeline/status")
    def pipeline_status():
        with Session(get_engine()) as session:
            last = session.scalar(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1))
            if last is None:
                return {"status": "never_run"}
            return {"run_id": last.run_id, "status": last.status, "command": last.command,
                    "started_at": last.started_at.isoformat(),
                    "completed_at": last.completed_at.isoformat() if last.completed_at else None,
                    "seasons": last.seasons, "row_counts": last.row_counts, "error": last.error}

    return app
