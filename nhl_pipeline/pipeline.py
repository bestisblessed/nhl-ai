"""Chief orchestration for offline seed loading and NHL backfills."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .client import NHLHTTPClient
from .config import Settings
from .db import create_schema, make_engine, session_scope
from .game_team import GameIngestor, TeamIngestor, validate_preseason_empty
from .models import PipelineRun, Season
from .persistence import upsert_games, upsert_seed, upsert_skater_rows, upsert_team_rows, upsert_team_season_rows
from .rosters_standings import RosterIngestor, StandingsIngestor
from .seasons import validate_season_coverage
from .seed import load_seed_csv
from .skaters import SkaterStatsIngestor


def _stats_client(settings: Settings) -> NHLHTTPClient:
    return NHLHTTPClient(timeout=settings.request_timeout_seconds, retries=settings.request_max_retries)


def _web_client(settings: Settings) -> NHLHTTPClient:
    return NHLHTTPClient("https://api-web.nhle.com/", timeout=settings.request_timeout_seconds, retries=settings.request_max_retries)


def register_seasons(settings: Settings, session, discovered: list[int] | None = None) -> tuple[int, ...]:
    expected = settings.season_ids
    actual = validate_season_coverage(expected, discovered or expected)
    for season_id in actual:
        existing = session.get(Season, (season_id, settings.game_type_id))
        state = "scheduled" if season_id == settings.backfill_through_season_id else "discovered"
        if existing is None:
            session.add(Season(season_id=season_id, game_type_id=settings.game_type_id, state=state))
        elif existing.state not in {"seeded", "complete"}:
            existing.state = state
    return actual


def load_seed(settings: Settings) -> int:
    engine = make_engine(settings)
    create_schema(engine)
    rows = load_seed_csv(settings.seed_csv_path, expected_season_id=settings.backfill_start_season_id)
    with session_scope(engine) as session:
        register_seasons(settings, session)
        count = upsert_seed(session, rows, game_type_id=settings.game_type_id)
        seed_season = session.get(Season, (settings.backfill_start_season_id, settings.game_type_id))
        if seed_season is not None:
            seed_season.state = "seeded"
    return count


def backfill(settings: Settings, *, offline_seed_only: bool = False) -> dict[str, int]:
    engine = make_engine(settings)
    create_schema(engine)
    seed_rows = load_seed_csv(settings.seed_csv_path, expected_season_id=settings.backfill_start_season_id)
    counts: dict[str, int] = {}
    with session_scope(engine) as session:
        register_seasons(settings, session)
        counts["seed"] = upsert_seed(session, seed_rows, game_type_id=settings.game_type_id)
    if offline_seed_only:
        return counts

    stats = _stats_client(settings)
    skaters = SkaterStatsIngestor(stats)
    games = GameIngestor(stats)
    teams = TeamIngestor(stats)
    for season_id in settings.season_ids:
        if season_id == settings.backfill_start_season_id:
            continue
        summary = skaters.fetch_season_summary(season_id, game_type_id=settings.game_type_id)
        toi = skaters.fetch_season_time_on_ice(season_id, game_type_id=settings.game_type_id)
        skater_rows = skaters.normalize_season(summary, toi)
        game_rows = games.fetch_season(season_id, game_type_id=settings.game_type_id)
        team_rows = teams.fetch_games(season_id, game_type_id=settings.game_type_id)
        season_team_rows = teams.fetch_season(season_id, game_type_id=settings.game_type_id)
        final_games = sum(1 for row in game_rows if row.state_id == 7)
        validate_preseason_empty(season_id=season_id, final_game_count=final_games, stat_records=skater_rows)
        with session_scope(engine) as session:
            upsert_skater_rows(session, skater_rows, game_type_id=settings.game_type_id)
            upsert_games(session, game_rows)
            upsert_team_rows(session, team_rows, season_id=season_id, game_type_id=settings.game_type_id)
            upsert_team_season_rows(session, season_team_rows, game_type_id=settings.game_type_id)
            state = "scheduled" if not skater_rows and not final_games else "complete"
            session.merge(Season(season_id=season_id, game_type_id=settings.game_type_id, state=state))
        counts[str(season_id)] = len(skater_rows)
    return counts


def refresh(settings: Settings) -> dict[str, int]:
    """Refresh the configured active season and the rolling correction window."""
    # A full backfill is idempotent and is the safest first-run behavior. Once
    # deployed, callers can narrow this to the active season/date window.
    return backfill(settings)
