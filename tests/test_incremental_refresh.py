from datetime import date

from sqlalchemy.orm import Session

from config import Settings
from ingestion.pipeline import _finish_run, _start_run, refresh_window, season_for_date
from storage.db import create_schema, make_engine
from storage.models import PipelineRun


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
