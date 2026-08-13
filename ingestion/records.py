"""Endpoint DTOs kept separate from SQLAlchemy persistence models."""
from dataclasses import asdict, dataclass
from typing import Any


class UpsertRecord:
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GameRecord(UpsertRecord):
    game_id: int; season_id: int; game_type_id: int; game_date: str | None
    # Stats REST calls this value easternStartTime; it has no timezone suffix.
    start_time_local: str | None; game_number: int | None; schedule_state_id: int | None
    state_id: int | None; home_team_id: int; visiting_team_id: int
    home_score: int | None; visiting_score: int | None; period: int | None


@dataclass(frozen=True)
class ScoreRecord(UpsertRecord):
    game_id: int; season_id: int; game_type_id: int; game_date: str | None
    game_state: str | None; schedule_state: str | None; start_time_utc: str | None
    home_team_id: int | None; visiting_team_id: int | None
    home_abbrev: str | None; visiting_abbrev: str | None
    home_score: int | None; visiting_score: int | None
    home_sog: int | None; visiting_sog: int | None


@dataclass(frozen=True)
class TeamGameRecord(UpsertRecord):
    game_id: int; team_id: int; game_date: str | None; home_road: str | None
    team_abbrev: str | None; opponent_team_abbrev: str | None; games_played: int | None
    goals_for: int | None; goals_against: int | None
    shots_for_per_game: float | None; shots_against_per_game: float | None
    wins: int | None; losses: int | None; ot_losses: int | None; points: int | None


@dataclass(frozen=True)
class TeamSeasonRecord(UpsertRecord):
    season_id: int; team_id: int; team_full_name: str | None; games_played: int | None
    goals_for: int | None; goals_against: int | None
    shots_for_per_game: float | None; shots_against_per_game: float | None
    wins: int | None; losses: int | None; ot_losses: int | None; points: int | None


@dataclass(frozen=True)
class StandingsRecord(UpsertRecord):
    snapshot_date: str; season_id: int | None; game_type_id: int | None
    team_id: int | None; team_abbrev: str | None; team_name: str | None
    conference: str | None; division: str | None; games_played: int | None
    wins: int | None; losses: int | None; ot_losses: int | None; points: int | None
    goals_for: int | None; goals_against: int | None; goal_differential: int | None


@dataclass(frozen=True)
class RosterRecord(UpsertRecord):
    snapshot_date: str; team_abbrev: str; player_id: int; roster_group: str
    first_name: str | None; last_name: str | None; sweater_number: int | None
    position_code: str | None; shoots_catches: str | None; birth_date: str | None
    height_inches: int | None; weight_pounds: int | None; source_season_id: int | None
