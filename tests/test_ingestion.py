from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nhl_api.ingestion import DataValidationError, load_and_clean, replace_snapshot
from nhl_api.models import Base, PlayerSeasonStats

DATA_FILE = Path(__file__).parents[1] / "data" / "data_dump.csv"


@pytest.fixture
def cleaned() -> pd.DataFrame:
    return load_and_clean(DATA_FILE)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as active_session:
        yield active_session


def test_cleaned_snapshot_has_expected_grain(cleaned: pd.DataFrame) -> None:
    assert cleaned.shape == (951, 22)
    assert cleaned["Season"].unique().tolist() == [20222023]
    assert not cleaned.duplicated(["playerId", "Season"]).any()


def test_cleaning_removes_empty_and_redundant_columns(cleaned: pd.DataFrame) -> None:
    assert not {"Unnamed: 13", "Unnamed: 18", "Shifts/GP", "MinPerGP"} & set(cleaned.columns)
    assert cleaned["S%"].isna().sum() == 28
    assert cleaned["FOW%"].isna().sum() == 382


def test_cleaning_preserves_ids_and_sanitizes_control_characters(cleaned: pd.DataFrame) -> None:
    row = cleaned.loc[cleaned["playerId"] == 8480226].iloc[0]
    assert row["Name"] == "Marian Studeni"
    assert all(ord(character) >= 32 for character in row["Name"])


def test_team_sequence_derivations(cleaned: pd.DataFrame) -> None:
    assert int((cleaned["team_count"] > 1).sum()) == 95
    eyssimont = cleaned.loc[cleaned["Name"] == "Michael Eyssimont"].iloc[0]
    assert eyssimont["Team"] == "WPG,SJS,TBL"
    assert eyssimont["team_count"] == 3
    assert eyssimont["final_team"] == "TBL"


def test_replace_snapshot_is_idempotent(cleaned: pd.DataFrame, session: Session) -> None:
    assert replace_snapshot(cleaned, session) == 951
    original_goal_total = session.scalar(select(func.sum(PlayerSeasonStats.goals)))
    assert replace_snapshot(cleaned, session) == 951
    count = session.scalar(select(func.count()).select_from(PlayerSeasonStats))
    reloaded_goal_total = session.scalar(select(func.sum(PlayerSeasonStats.goals)))
    assert count == 951
    assert reloaded_goal_total == original_goal_total


def test_replace_snapshot_persists_changed_content_without_duplicates(
    cleaned: pd.DataFrame, session: Session
) -> None:
    replace_snapshot(cleaned, session)
    changed = cleaned.copy()
    changed.loc[0, ["G", "P", "S%"]] = [1, 3, 0.5]
    replace_snapshot(changed, session)

    stored = session.get(
        PlayerSeasonStats,
        (int(changed.loc[0, "playerId"]), int(changed.loc[0, "Season"])),
    )
    count = session.scalar(select(func.count()).select_from(PlayerSeasonStats))
    assert stored is not None
    assert stored.goals == 1
    assert stored.points == 3
    assert stored.shooting_pct == 0.5
    assert count == 951


def test_replace_snapshot_reconciles_removed_rows(cleaned: pd.DataFrame, session: Session) -> None:
    replace_snapshot(cleaned, session)
    replace_snapshot(cleaned.iloc[:-1].copy(), session)
    count = session.scalar(select(func.count()).select_from(PlayerSeasonStats))
    assert count == 950


def test_replace_snapshot_rolls_back_on_database_constraint_failure(
    cleaned: pd.DataFrame, session: Session
) -> None:
    replace_snapshot(cleaned, session)
    invalid = cleaned.copy()
    invalid.loc[0, "P"] = 999

    with pytest.raises(IntegrityError):
        replace_snapshot(invalid, session)

    count = session.scalar(select(func.count()).select_from(PlayerSeasonStats))
    original_points = session.scalar(
        select(PlayerSeasonStats.points).where(
            PlayerSeasonStats.player_id == int(cleaned.loc[0, "playerId"]),
            PlayerSeasonStats.season == int(cleaned.loc[0, "Season"]),
        )
    )
    assert count == 951
    assert original_points == int(cleaned.loc[0, "P"])


def test_duplicate_key_is_rejected_before_database_write(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    source_lines = DATA_FILE.read_text().splitlines()
    path.write_text("\n".join([*source_lines, source_lines[1]]) + "\n")

    with pytest.raises(DataValidationError, match="Duplicate"):
        load_and_clean(path)


def test_changed_header_is_rejected(tmp_path: Path) -> None:
    source = DATA_FILE.read_text()
    path = tmp_path / "changed-header.csv"
    path.write_text(source.replace("playerId,Name", "id,Name", 1))

    with pytest.raises(DataValidationError, match="header"):
        load_and_clean(path)


def test_populated_placeholder_column_is_rejected(tmp_path: Path) -> None:
    lines = DATA_FILE.read_text().splitlines()
    first_row = lines[1].split(",")
    first_row[13] = "unexpected"
    lines[1] = ",".join(first_row)
    path = tmp_path / "populated-placeholder.csv"
    path.write_text("\n".join(lines) + "\n")

    with pytest.raises(DataValidationError, match="blank export columns"):
        load_and_clean(path)
