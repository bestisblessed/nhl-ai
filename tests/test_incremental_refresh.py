from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import ingestion.pipeline as pipeline
from config import Settings
from ingestion.pipeline import _finish_run, _start_run, backfill, refresh_window, season_for_date
from storage.db import create_schema, make_engine
from storage.models import PipelineRun, Season


def test_normal_daily_window_is_d1_through_d3():
    assert refresh_window(
        date(2026, 8, 13),
        lookback_days=3,
        max_recovery_days=14,
    ) == (date(2026, 8, 10), date(2026, 8, 12))


def test_missed_run_extends_window_and_caps_recovery():
    assert refresh_window(
        date(2026, 8, 13),
        lookback_days=3,
        max_recovery_days=14,
        last_success_date=date(2026, 8, 6),
    ) == (date(2026, 8, 6), date(2026, 8, 12))
    assert refresh_window(
        date(2026, 8, 13),
        lookback_days=3,
        max_recovery_days=14,
        last_success_date=date(2025, 1, 1),
    ) == (date(2026, 7, 30), date(2026, 8, 12))


def test_future_success_checkpoint_does_not_change_window():
    assert refresh_window(
        date(2026, 8, 13),
        lookback_days=3,
        max_recovery_days=14,
        last_success_date=date(2026, 8, 14),
    ) == (date(2026, 8, 10), date(2026, 8, 12))


def test_season_for_date_handles_both_calendar_years():
    assert season_for_date(date(2025, 10, 7)) == 20252026
    assert season_for_date(date(2026, 4, 16)) == 20252026
    assert season_for_date(date(2026, 8, 13)) == 20262027


def test_pipeline_run_failure_is_persisted_for_status_api(tmp_path):
    engine = make_engine(Settings(database_url=f"sqlite:///{tmp_path / 'runs.db'}"))
    create_schema(engine)
    run_id = _start_run(engine, command="refresh", seasons=[20262027])
    _finish_run(engine, run_id, status="failed", error="upstream unavailable")

    with Session(engine) as session:
        run = session.get(PipelineRun, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.completed_at is not None
        assert run.error == "upstream unavailable"


def test_offline_seed_backfill_records_a_successful_pipeline_run(tmp_path):
    settings = Settings(
        seed_csv_path=Path(__file__).parents[1] / "data" / "data_dump.csv",
        database_url=f"sqlite:///{tmp_path / 'backfill.db'}",
    )
    backfill(settings, offline_seed_only=True)

    engine = make_engine(settings)
    with Session(engine) as session:
        run = session.scalar(select(PipelineRun).where(PipelineRun.command == "backfill"))
        assert run is not None
        assert run.status == "succeeded"


def test_partial_backfill_failure_does_not_look_initialized(tmp_path, monkeypatch):
    """A backfill that dies after seeding must not be mistaken for a completed one.

    ``register_seasons`` writes ``seasons`` rows for every configured season
    before any historical season is actually fetched, so a bootstrap check
    that only asks "does the seasons table have a row" would treat this
    partial, failed run as fully initialized and never retry the seasons
    that were never processed. The bootstrap check must instead require a
    successful ``backfill`` pipeline run.
    """

    settings = Settings(
        seed_csv_path=Path(__file__).parents[1] / "data" / "data_dump.csv",
        database_url=f"sqlite:///{tmp_path / 'partial.db'}",
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated NHL API outage")

    monkeypatch.setattr(pipeline, "fetch_team_abbreviations", _boom)

    with pytest.raises(RuntimeError, match="simulated NHL API outage"):
        backfill(settings)

    engine = make_engine(settings)
    with Session(engine) as session:
        assert session.scalar(select(Season)) is not None, (
            "seasons rows already exist after the partial failure, which is exactly "
            "why checking for their mere existence is not a safe readiness signal"
        )
        run = session.scalar(select(PipelineRun).where(PipelineRun.command == "backfill"))
        assert run is not None
        assert run.status == "failed"

    with engine.connect() as connection:
        succeeded = connection.execute(
            text("SELECT 1 FROM pipeline_runs WHERE command = 'backfill' AND status = 'succeeded' LIMIT 1")
        ).first()
    assert succeeded is None
