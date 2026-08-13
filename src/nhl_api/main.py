from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from nhl_api.analytics import (
    DEFAULT_SEASON,
    goals_leaders,
    inferred_roster,
    penalty_rate_leaders,
    team_change_leaders,
    team_rankings,
)
from nhl_api.database import get_session
from nhl_api.ingestion import TEAM_CODES
from nhl_api.models import PlayerSeasonStats
from nhl_api.schemas import (
    GoalLeader,
    HealthResponse,
    InferredRosterResponse,
    PenaltyRateLeader,
    TeamChangeLeader,
    TeamRankingsResponse,
)

app = FastAPI(
    title="NHL Analytics API",
    description=(
        "Analyst-focused NHL player-season API. Team rosters and rankings are explicitly "
        "labeled where the aggregate source data requires inference or partial totals."
    ),
    version="0.1.0",
)

SessionDependency = Annotated[Session, Depends(get_session)]


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(session: SessionDependency) -> HealthResponse:
    session.execute(text("SELECT 1"))
    row_count = session.scalar(select(func.count()).select_from(PlayerSeasonStats)) or 0
    return HealthResponse(status="ok", database="connected", rows_loaded=row_count)


@app.get("/players/goals-leaders", response_model=list[GoalLeader], tags=["players"])
def get_goals_leaders(
    session: SessionDependency,
    season: Annotated[int, Query(description="NHL season identifier")] = DEFAULT_SEASON,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    min_games: Annotated[int, Query(ge=1)] = 1,
) -> list[GoalLeader]:
    """Rank skaters by goals with points, name, and ID as deterministic tiebreakers."""
    leaders = goals_leaders(session, season=season, limit=limit, min_games=min_games)
    if not leaders:
        raise HTTPException(status_code=404, detail="No player rows match those filters")
    return leaders


@app.get(
    "/players/penalty-rate-leaders",
    response_model=list[PenaltyRateLeader],
    tags=["players"],
)
def get_penalty_rate_leaders(
    session: SessionDependency,
    season: Annotated[int, Query(description="NHL season identifier")] = DEFAULT_SEASON,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    min_games: Annotated[int, Query(ge=1)] = 10,
) -> list[PenaltyRateLeader]:
    """Rank PIM / (GP * SecPerGP / 60); PIM is minutes, not penalty events."""
    leaders = penalty_rate_leaders(session, season=season, limit=limit, min_games=min_games)
    if not leaders:
        raise HTTPException(status_code=404, detail="No player rows match those filters")
    return leaders


@app.get("/players/team-changes", response_model=list[TeamChangeLeader], tags=["players"])
def get_team_change_leaders(
    session: SessionDependency,
    season: Annotated[int, Query(description="NHL season identifier")] = DEFAULT_SEASON,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[TeamChangeLeader]:
    """Rank multi-team rows; team changes are inferred as team token count minus one."""
    leaders = team_change_leaders(session, season=season, limit=limit)
    if not leaders:
        raise HTTPException(status_code=404, detail="No multi-team player rows match that season")
    return leaders


@app.get(
    "/teams/{team_code}/roster",
    response_model=InferredRosterResponse,
    tags=["teams"],
)
def get_inferred_roster(
    session: SessionDependency,
    team_code: Annotated[str, Path(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")],
    season: Annotated[int, Query(description="NHL season identifier")] = DEFAULT_SEASON,
) -> InferredRosterResponse:
    """Return a season-end roster inferred from the final team token in each row."""
    if team_code not in TEAM_CODES:
        raise HTTPException(status_code=404, detail="Unknown team code")
    roster = inferred_roster(session, season=season, team_code=team_code)
    if not roster.players:
        raise HTTPException(
            status_code=404, detail="No inferred roster matches that team and season"
        )
    return roster


@app.get("/teams/rankings", response_model=TeamRankingsResponse, tags=["teams"])
def get_team_rankings(
    session: SessionDependency,
    metric: Annotated[Literal["goals", "shots"], Query()] = "goals",
    season: Annotated[int, Query(description="NHL season identifier")] = DEFAULT_SEASON,
) -> TeamRankingsResponse:
    """Return partial lower-bound totals using only unambiguous single-team rows."""
    rankings = team_rankings(session, season=season, metric=metric)
    if not rankings.teams:
        raise HTTPException(status_code=404, detail="No team rows match that season")
    return rankings
