from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from sqlalchemy import Float, cast, desc, func, select
from sqlalchemy.orm import Session

from nhl_api.models import PlayerSeasonStats
from nhl_api.schemas import (
    GoalLeader,
    InferredRosterResponse,
    PenaltyRateLeader,
    RosterPlayer,
    TeamChangeLeader,
    TeamRanking,
    TeamRankingsResponse,
)

DEFAULT_SEASON = 20222023


def _team_codes(value: str) -> list[str]:
    return value.split(",")


def _ranked(values: Sequence[float | int]) -> list[int]:
    ranks: list[int] = []
    previous: float | int | None = None
    current_rank = 0
    for value in values:
        if value != previous:
            current_rank += 1
            previous = value
        ranks.append(current_rank)
    return ranks


def goals_leaders(session: Session, *, season: int, limit: int, min_games: int) -> list[GoalLeader]:
    players = session.scalars(
        select(PlayerSeasonStats)
        .where(
            PlayerSeasonStats.season == season,
            PlayerSeasonStats.games_played >= min_games,
        )
        .order_by(
            desc(PlayerSeasonStats.goals),
            desc(PlayerSeasonStats.points),
            PlayerSeasonStats.name,
            PlayerSeasonStats.player_id,
        )
        .limit(limit)
    ).all()
    ranks = _ranked([player.goals for player in players])
    return [
        GoalLeader(
            rank=rank,
            player_id=player.player_id,
            name=player.name,
            team_codes=_team_codes(player.team_codes),
            position=player.position,
            games_played=player.games_played,
            goals=player.goals,
        )
        for rank, player in zip(ranks, players, strict=True)
    ]


def penalty_rate_leaders(
    session: Session, *, season: int, limit: int, min_games: int
) -> list[PenaltyRateLeader]:
    total_minutes = (
        cast(PlayerSeasonStats.games_played, Float) * PlayerSeasonStats.seconds_per_game / 60.0
    )
    rate = cast(PlayerSeasonStats.penalty_minutes, Float) / total_minutes
    rows = session.execute(
        select(PlayerSeasonStats, total_minutes.label("total_minutes"), rate.label("rate"))
        .where(
            PlayerSeasonStats.season == season,
            PlayerSeasonStats.games_played >= min_games,
        )
        .order_by(desc(rate), desc(PlayerSeasonStats.penalty_minutes), PlayerSeasonStats.name)
        .limit(limit)
    ).all()
    ranks = _ranked([float(row.rate) for row in rows])
    return [
        PenaltyRateLeader(
            rank=rank,
            player_id=row.PlayerSeasonStats.player_id,
            name=row.PlayerSeasonStats.name,
            team_codes=_team_codes(row.PlayerSeasonStats.team_codes),
            games_played=row.PlayerSeasonStats.games_played,
            penalty_minutes=row.PlayerSeasonStats.penalty_minutes,
            total_ice_minutes=round(float(row.total_minutes), 3),
            penalty_minutes_per_minute=round(float(row.rate), 6),
            penalty_minutes_per_60=round(float(row.rate) * 60.0, 6),
        )
        for rank, row in zip(ranks, rows, strict=True)
    ]


def team_change_leaders(session: Session, *, season: int, limit: int) -> list[TeamChangeLeader]:
    players = session.scalars(
        select(PlayerSeasonStats)
        .where(PlayerSeasonStats.season == season, PlayerSeasonStats.team_count > 1)
        .order_by(desc(PlayerSeasonStats.team_count), PlayerSeasonStats.name)
        .limit(limit)
    ).all()
    ranks = _ranked([player.team_count for player in players])
    return [
        TeamChangeLeader(
            rank=rank,
            player_id=player.player_id,
            name=player.name,
            team_codes=_team_codes(player.team_codes),
            team_count=player.team_count,
            team_changes=player.team_count - 1,
        )
        for rank, player in zip(ranks, players, strict=True)
    ]


def inferred_roster(session: Session, *, season: int, team_code: str) -> InferredRosterResponse:
    players = session.scalars(
        select(PlayerSeasonStats)
        .where(
            PlayerSeasonStats.season == season,
            PlayerSeasonStats.final_team == team_code,
        )
        .order_by(PlayerSeasonStats.position, PlayerSeasonStats.name)
    ).all()
    return InferredRosterResponse(
        team_code=team_code,
        season=season,
        inference=(
            "Season-end roster inferred from each player's final listed team; "
            "this is not an official current roster."
        ),
        player_count=len(players),
        players=[
            RosterPlayer(
                player_id=player.player_id,
                name=player.name,
                position=player.position,
                games_played=player.games_played,
                team_codes=_team_codes(player.team_codes),
            )
            for player in players
        ],
    )


def team_rankings(
    session: Session, *, season: int, metric: Literal["goals", "shots"]
) -> TeamRankingsResponse:
    metric_column = PlayerSeasonStats.goals if metric == "goals" else PlayerSeasonStats.shots
    rows = session.execute(
        select(
            PlayerSeasonStats.final_team.label("team_code"),
            func.sum(metric_column).label("total"),
            func.count().label("players_included"),
        )
        .where(PlayerSeasonStats.season == season, PlayerSeasonStats.team_count == 1)
        .group_by(PlayerSeasonStats.final_team)
        .order_by(desc("total"), PlayerSeasonStats.final_team)
    ).all()
    excluded = (
        session.scalar(
            select(func.count())
            .select_from(PlayerSeasonStats)
            .where(PlayerSeasonStats.season == season, PlayerSeasonStats.team_count > 1)
        )
        or 0
    )
    ranks = _ranked([int(row.total) for row in rows])
    return TeamRankingsResponse(
        season=season,
        metric=metric,
        warning=(
            "Lower-bound totals from single-team player rows only. Multi-team rows contain "
            "combined season totals without team splits and are excluded."
        ),
        excluded_multi_team_players=excluded,
        teams=[
            TeamRanking(
                partial_rank=rank,
                team_code=row.team_code,
                lower_bound_total=int(row.total),
                players_included=int(row.players_included),
            )
            for rank, row in zip(ranks, rows, strict=True)
        ],
    )
