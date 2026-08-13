from __future__ import annotations

import argparse
import csv
import unicodedata
from pathlib import Path

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from nhl_api.database import engine
from nhl_api.models import Base, PlayerSeasonStats

RAW_COLUMNS = [
    "playerId",
    "Name",
    "Team",
    "Pos",
    "GP",
    "G",
    "A",
    "P",
    "+/-",
    "PIM",
    "PPG",
    "SHG",
    "GWG",
    "",
    "S",
    "S%",
    "SecPerGP",
    "MinPerGP",
    "",
    "Shifts/GP",
    "FOW%",
    "Season",
    "PPP",
    "SHP",
]

DROP_COLUMNS = ["Unnamed: 13", "Unnamed: 18", "Shifts/GP", "MinPerGP"]
POSITIONS = {"C", "D", "L", "R"}
TEAM_CODES = {
    "ANA",
    "ARI",
    "BOS",
    "BUF",
    "CAR",
    "CBJ",
    "CGY",
    "CHI",
    "COL",
    "DAL",
    "DET",
    "EDM",
    "FLA",
    "LAK",
    "MIN",
    "MTL",
    "NJD",
    "NSH",
    "NYI",
    "NYR",
    "OTT",
    "PHI",
    "PIT",
    "SEA",
    "SJS",
    "STL",
    "TBL",
    "TOR",
    "VAN",
    "VGK",
    "WPG",
    "WSH",
}


class DataValidationError(ValueError):
    """Raised when the source snapshot violates its documented contract."""


def _validate_header(path: Path) -> None:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        header = next(csv.reader(stream), None)
    if header != RAW_COLUMNS:
        raise DataValidationError("CSV header does not match the expected 24-column NHL export")


def _clean_name(value: str) -> str:
    cleaned = "".join(char for char in value.strip() if unicodedata.category(char) != "Cc")
    if not cleaned:
        raise DataValidationError("Player name is empty after removing control characters")
    return cleaned


def _nullable_float(value: object) -> float | None:
    return None if pd.isna(value) else float(value)


def load_and_clean(path: Path | str) -> pd.DataFrame:
    source = Path(path)
    _validate_header(source)
    frame = pd.read_csv(source, na_values=["None"])

    if frame.shape[1] != 24:
        raise DataValidationError(f"Expected 24 columns, found {frame.shape[1]}")
    if frame.empty:
        raise DataValidationError("CSV contains no player-season rows")
    if any(frame[column].notna().any() for column in ["Unnamed: 13", "Unnamed: 18", "Shifts/GP"]):
        raise DataValidationError("Expected blank export columns contain data")

    frame = frame.drop(columns=DROP_COLUMNS).copy()
    frame["Name"] = frame["Name"].map(_clean_name)

    if frame[["playerId", "Season"]].isna().any().any():
        raise DataValidationError("playerId and Season are required")
    if frame.duplicated(["playerId", "Season"]).any():
        raise DataValidationError("Duplicate (playerId, Season) rows found")
    if not set(frame["Pos"]).issubset(POSITIONS):
        raise DataValidationError("Unsupported player position found")

    team_lists = frame["Team"].str.split(",")
    invalid_teams = sorted(
        {team for teams in team_lists for team in teams if team not in TEAM_CODES}
    )
    if invalid_teams:
        raise DataValidationError(f"Unsupported team codes: {', '.join(invalid_teams)}")
    frame["team_count"] = team_lists.str.len()
    frame["final_team"] = team_lists.str[-1]

    integer_columns = [
        "playerId",
        "GP",
        "G",
        "A",
        "P",
        "+/-",
        "PIM",
        "PPG",
        "SHG",
        "GWG",
        "S",
        "Season",
        "PPP",
        "SHP",
    ]
    for column in integer_columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise").astype(int)
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"{column} contains a non-integer value") from exc

    float_columns = ["S%", "SecPerGP", "FOW%"]
    for column in float_columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"{column} contains a non-numeric value") from exc

    if (frame["GP"] <= 0).any():
        raise DataValidationError("GP must be positive")
    nonnegative = ["G", "A", "P", "PIM", "PPG", "SHG", "GWG", "S", "PPP", "SHP"]
    if (frame[nonnegative] < 0).any().any():
        raise DataValidationError("Count statistics must be nonnegative")
    if (frame["P"] != frame["G"] + frame["A"]).any():
        raise DataValidationError("P must equal G + A")
    if (frame["S"] < frame["G"]).any():
        raise DataValidationError("Shots cannot be lower than goals")
    if ((frame["S%"].notna()) & ~frame["S%"].between(0, 1)).any():
        raise DataValidationError("S% must be between 0 and 1")
    if ((frame["FOW%"].notna()) & ~frame["FOW%"].between(0, 1)).any():
        raise DataValidationError("FOW% must be between 0 and 1")
    if (frame["SecPerGP"] <= 0).any():
        raise DataValidationError("SecPerGP must be positive")

    expected_shooting = frame["G"] / frame["S"].where(frame["S"] > 0)
    shooting_difference = (frame["S%"] - expected_shooting).abs()
    if (shooting_difference.dropna() > 0.00001).any():
        raise DataValidationError("S% does not match G / S")
    if frame.loc[frame["S"] == 0, "S%"].notna().any():
        raise DataValidationError("S% must be null when shots are zero")

    return frame.reset_index(drop=True)


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in frame.itertuples(index=False, name=None):
        values = dict(zip(frame.columns, row, strict=True))
        records.append(
            {
                "player_id": int(values["playerId"]),
                "season": int(values["Season"]),
                "name": str(values["Name"]),
                "team_codes": str(values["Team"]),
                "final_team": str(values["final_team"]),
                "team_count": int(values["team_count"]),
                "position": str(values["Pos"]),
                "games_played": int(values["GP"]),
                "goals": int(values["G"]),
                "assists": int(values["A"]),
                "points": int(values["P"]),
                "plus_minus": int(values["+/-"]),
                "penalty_minutes": int(values["PIM"]),
                "power_play_goals": int(values["PPG"]),
                "short_handed_goals": int(values["SHG"]),
                "game_winning_goals": int(values["GWG"]),
                "shots": int(values["S"]),
                "shooting_pct": _nullable_float(values["S%"]),
                "seconds_per_game": float(values["SecPerGP"]),
                "faceoff_pct": _nullable_float(values["FOW%"]),
                "power_play_points": int(values["PPP"]),
                "short_handed_points": int(values["SHP"]),
            }
        )
    return records


def replace_snapshot(frame: pd.DataFrame, session: Session) -> int:
    records = _records(frame)
    seasons = sorted({int(season) for season in frame["Season"]})
    try:
        session.execute(delete(PlayerSeasonStats).where(PlayerSeasonStats.season.in_(seasons)))
        session.bulk_insert_mappings(PlayerSeasonStats, records)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(records)


def ingest(path: Path | str) -> int:
    frame = load_and_clean(path)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        return replace_snapshot(frame, session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load an NHL player-season CSV snapshot")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    loaded = ingest(args.path)
    print(f"Loaded {loaded} player-season rows from {args.path}")


if __name__ == "__main__":
    main()
