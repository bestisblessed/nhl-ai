from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    rows_loaded: int


class GoalLeader(BaseModel):
    rank: int
    player_id: int
    name: str
    team_codes: list[str]
    position: str
    games_played: int
    goals: int


class PenaltyRateLeader(BaseModel):
    rank: int
    player_id: int
    name: str
    team_codes: list[str]
    games_played: int
    penalty_minutes: int
    total_ice_minutes: float
    penalty_minutes_per_minute: float
    penalty_minutes_per_60: float


class TeamChangeLeader(BaseModel):
    rank: int
    player_id: int
    name: str
    team_codes: list[str]
    team_count: int
    team_changes: int


class RosterPlayer(BaseModel):
    player_id: int
    name: str
    position: str
    games_played: int
    team_codes: list[str]


class InferredRosterResponse(BaseModel):
    team_code: str
    season: int
    is_inferred: Literal[True] = True
    inference: str
    player_count: int
    players: list[RosterPlayer]


class TeamRanking(BaseModel):
    partial_rank: int
    team_code: str
    lower_bound_total: int
    players_included: int


class TeamRankingsResponse(BaseModel):
    season: int
    metric: Literal["goals", "shots"]
    is_partial: Literal[True] = True
    warning: str
    excluded_multi_team_players: int
    teams: list[TeamRanking]
