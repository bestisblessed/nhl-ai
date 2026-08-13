"""Chief orchestration for offline seed, historical backfill, and daily refresh."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .client import NHLHTTPClient
from config import Settings
from storage.db import create_schema, make_engine, session_scope
from .games import GameIngestor, ScoreIngestor
from .rosters import RosterIngestor
from .standings import StandingsIngestor
from .teams import TeamIngestor, fetch_team_abbreviations, validate_preseason_empty
from storage.models import PipelineRun, Season
from storage.persistence import (
    upsert_games,
    upsert_player_game_rows,
    upsert_roster_rows,
    upsert_score_rows,
    upsert_seed,
    upsert_skater_rows,
    upsert_standings_rows,
    upsert_team_rows,
    upsert_team_season_rows,
)
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
        session.flush()
        seed_season = session.get(Season, (settings.backfill_start_season_id, settings.game_type_id))
        if seed_season is not None:
            seed_season.state = "seeded"
    return count


def backfill(settings: Settings, *, offline_seed_only: bool = False) -> dict[str, int]:
    """Load every configured season and record whether the run fully completed.

    Callers (notably the daily-refresh workflow) use the recorded
    ``pipeline_runs`` row to decide whether a full backfill ever succeeded.
    Without this record, a run that dies partway through the season loop
    still leaves ``seasons`` rows behind (via ``register_seasons``), which
    would make a merely-started backfill look indistinguishable from a
    completed one and silently strand the unprocessed seasons forever.
    """

    engine = make_engine(settings)
    create_schema(engine)
    run_id = _start_run(engine, command="backfill", seasons=list(settings.season_ids))
    try:
        seed_rows = load_seed_csv(settings.seed_csv_path, expected_season_id=settings.backfill_start_season_id)
        counts: dict[str, int] = {}
        with session_scope(engine) as session:
            register_seasons(settings, session)
            counts["seed"] = upsert_seed(session, seed_rows, game_type_id=settings.game_type_id)
            session.flush()
            seed_season = session.get(Season, (settings.backfill_start_season_id, settings.game_type_id))
            if seed_season is not None:
                seed_season.state = "seeded"
        if offline_seed_only:
            _finish_run(engine, run_id, status="succeeded", counts=counts)
            return counts

        stats = _stats_client(settings)
        skaters = SkaterStatsIngestor(stats)
        games = GameIngestor(stats)
        teams = TeamIngestor(stats)
        team_abbrevs = fetch_team_abbreviations(stats)
        for season_id in settings.season_ids:
            is_seed_season = season_id == settings.backfill_start_season_id
            if is_seed_season:
                skater_rows = seed_rows
                api_skater_rows = None
            else:
                summary = skaters.fetch_season_summary(season_id, game_type_id=settings.game_type_id)
                toi = skaters.fetch_season_time_on_ice(season_id, game_type_id=settings.game_type_id)
                api_skater_rows = skaters.normalize_season(summary, toi)
                skater_rows = api_skater_rows
            game_rows = games.fetch_season(season_id, game_type_id=settings.game_type_id)
            team_rows = teams.fetch_games(season_id, game_type_id=settings.game_type_id)
            season_team_rows = teams.fetch_season(season_id, game_type_id=settings.game_type_id)
            final_games = sum(1 for row in game_rows if row.state_id == 7)
            validate_preseason_empty(season_id=season_id, final_game_count=final_games, stat_records=skater_rows)
            with session_scope(engine) as session:
                if api_skater_rows is not None:
                    upsert_skater_rows(session, api_skater_rows, game_type_id=settings.game_type_id)
                upsert_games(session, game_rows)
                upsert_team_rows(
                    session,
                    team_rows,
                    season_id=season_id,
                    team_abbrevs=team_abbrevs,
                    game_type_id=settings.game_type_id,
                )
                upsert_team_season_rows(
                    session,
                    season_team_rows,
                    team_abbrevs=team_abbrevs,
                    game_type_id=settings.game_type_id,
                )
                state = "seeded" if is_seed_season else (
                    "scheduled" if not skater_rows and not final_games else "complete"
                )
                session.merge(Season(season_id=season_id, game_type_id=settings.game_type_id, state=state))
            if not is_seed_season:
                counts[str(season_id)] = len(skater_rows)
        _finish_run(engine, run_id, status="succeeded", counts=counts)
        return counts
    except Exception as exc:
        _finish_run(engine, run_id, status="failed", error=str(exc))
        raise


def refresh_window(
    as_of: date,
    *,
    lookback_days: int,
    max_recovery_days: int,
    last_success_date: date | None = None,
) -> tuple[date, date]:
    """Return an inclusive correction window ending yesterday.

    A missed run extends the normal D-1..D-N overlap back to the last successful
    daily run, capped so a long outage cannot silently become a historical
    backfill.
    """

    end = as_of - timedelta(days=1)
    normal_start = as_of - timedelta(days=lookback_days)
    recovery_floor = as_of - timedelta(days=max_recovery_days)
    start = normal_start
    if last_success_date is not None and last_success_date < as_of:
        start = min(start, last_success_date)
    return max(start, recovery_floor), end


def season_for_date(value: date) -> int:
    """Map a date to the NHL season spanning that calendar date."""

    start_year = value.year if value.month >= 7 else value.year - 1
    return int(f"{start_year}{start_year + 1}")


def _local_today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.daily_timezone)).date()


def _last_successful_daily_date(engine, settings: Settings) -> date | None:
    with session_scope(engine) as session:
        completed = session.scalar(
            select(PipelineRun.completed_at)
            .where(PipelineRun.command == "refresh", PipelineRun.status == "succeeded")
            .order_by(PipelineRun.completed_at.desc())
            .limit(1)
        )
    if completed is None:
        return None
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return completed.astimezone(ZoneInfo(settings.daily_timezone)).date()


def _start_run(engine, *, command: str, seasons: list[int]) -> str:
    run_id = str(uuid4())
    with session_scope(engine) as session:
        session.add(PipelineRun(
            run_id=run_id,
            command=command,
            status="running",
            started_at=datetime.now(UTC),
            seasons=seasons,
        ))
    return run_id


def _finish_run(
    engine,
    run_id: str,
    *,
    status: str,
    counts: dict[str, object] | None = None,
    error: str | None = None,
) -> None:
    with session_scope(engine) as session:
        run = session.get(PipelineRun, run_id)
        if run is None:
            raise RuntimeError(f"pipeline run disappeared: {run_id}")
        run.status = status
        run.completed_at = datetime.now(UTC)
        run.row_counts = counts
        run.error = error[:2000] if error else None


def refresh(settings: Settings, *, as_of: date | None = None) -> dict[str, object]:
    """Run the incremental morning refresh without re-fetching old seasons.

    Daily mode processes D-1 through D-3 (or a capped recovery window), then
    refreshes the candidate season's cumulative totals plus current standings
    and rosters. ``as_of`` is an explicit replay/testing date and never changes
    the recovery checkpoint used by normal scheduled runs.
    """

    engine = make_engine(settings)
    create_schema(engine)
    run_date = _local_today(settings)
    window_as_of = as_of or run_date
    candidate_season = season_for_date(window_as_of)
    if candidate_season not in settings.season_ids:
        raise ValueError(
            f"refresh season {candidate_season} is outside configured range "
            f"{settings.season_ids[0]}..{settings.season_ids[-1]}"
        )

    explicit_replay = as_of is not None
    command = "refresh-as-of" if explicit_replay else "refresh"
    last_success = None if explicit_replay else _last_successful_daily_date(engine, settings)
    window_start, window_end = refresh_window(
        window_as_of,
        lookback_days=settings.daily_correction_lookback_days,
        max_recovery_days=settings.daily_max_recovery_days,
        last_success_date=last_success,
    )
    refresh_dates = [
        window_start + timedelta(days=offset)
        for offset in range((window_end - window_start).days + 1)
    ]
    run_id = _start_run(engine, command=command, seasons=[candidate_season])

    try:
        stats_client = _stats_client(settings)
        web_client = _web_client(settings)
        scores = ScoreIngestor(web_client)
        skaters = SkaterStatsIngestor(stats_client)
        teams = TeamIngestor(stats_client)
        standings = StandingsIngestor(web_client)
        rosters = RosterIngestor(web_client)
        team_abbrevs = fetch_team_abbreviations(stats_client)
        team_ids = {abbrev: team_id for team_id, abbrev in team_abbrevs.items()}

        score_rows = []
        player_game_rows = []
        team_game_rows: list[tuple[int, list]] = []
        touched_seasons: set[int] = set()
        for refresh_date in refresh_dates:
            day = refresh_date.isoformat()
            daily_scores = [
                row for row in scores.fetch_date(day)
                if row.game_type_id == settings.game_type_id
                and row.season_id in settings.season_ids
            ]
            score_rows.extend(daily_scores)
            seasons_on_date = sorted({row.season_id for row in daily_scores})
            for season_id in seasons_on_date:
                touched_seasons.add(season_id)
                raw_players = skaters.fetch_game_summary(
                    season_id,
                    game_date=day,
                    game_type_id=settings.game_type_id,
                )
                player_game_rows.extend(
                    skaters.normalize_games(
                        raw_players,
                        team_ids_by_abbrev=team_ids,
                        game_type_id=settings.game_type_id,
                    )
                )
                team_game_rows.append((
                    season_id,
                    teams.fetch_date(
                        season_id,
                        day,
                        game_type_id=settings.game_type_id,
                    ),
                ))

        season_summary = skaters.fetch_season_summary(
            candidate_season,
            game_type_id=settings.game_type_id,
        )
        season_toi = skaters.fetch_season_time_on_ice(
            candidate_season,
            game_type_id=settings.game_type_id,
        )
        skater_season_rows = skaters.normalize_season(season_summary, season_toi)
        team_season_rows = teams.fetch_season(
            candidate_season,
            game_type_id=settings.game_type_id,
        )
        if bool(skater_season_rows) != bool(team_season_rows):
            raise ValueError(
                f"season {candidate_season} aggregate reports disagree: "
                f"{len(skater_season_rows)} skaters, {len(team_season_rows)} teams"
            )

        snapshot_date = run_date.isoformat()
        if explicit_replay:
            standing_rows = standings.fetch_date(
                window_as_of.isoformat(),
                team_ids=team_ids,
            )
        else:
            standing_rows = standings.fetch_now(
                snapshot_date=snapshot_date,
                team_ids=team_ids,
            )
        active_team_abbrevs = sorted({
            row.team_abbrev for row in standing_rows
            if row.team_abbrev and row.team_abbrev in team_ids
        })
        roster_rows = []
        for team_abbrev in active_team_abbrevs:
            roster_rows.extend(
                rosters.fetch_current(team_abbrev, snapshot_date=snapshot_date)
            )

        counts: dict[str, object] = {
            "run_id": run_id,
            "as_of_date": window_as_of.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "dates_checked": len(refresh_dates),
            "season_id": candidate_season,
            "games": len(score_rows),
            "player_game_stats": len(player_game_rows),
            "team_game_stats": sum(len(rows) for _, rows in team_game_rows),
            "player_season_stats": len(skater_season_rows),
            "team_season_stats": len(team_season_rows),
            "standings_snapshots": len(standing_rows),
            "roster_snapshots": len(roster_rows),
        }

        with session_scope(engine) as session:
            upsert_score_rows(session, score_rows)
            upsert_player_game_rows(session, player_game_rows)
            for season_id, rows in team_game_rows:
                upsert_team_rows(
                    session,
                    rows,
                    season_id=season_id,
                    team_abbrevs=team_abbrevs,
                    game_type_id=settings.game_type_id,
                )
            upsert_skater_rows(
                session,
                skater_season_rows,
                game_type_id=settings.game_type_id,
            )
            upsert_team_season_rows(
                session,
                team_season_rows,
                team_abbrevs=team_abbrevs,
                game_type_id=settings.game_type_id,
            )
            upsert_standings_rows(session, standing_rows, team_ids=team_ids)
            upsert_roster_rows(
                session,
                roster_rows,
                team_ids=team_ids,
                season_id=season_for_date(run_date),
            )
            season = session.get(Season, (candidate_season, settings.game_type_id))
            if season is None:
                session.add(Season(
                    season_id=candidate_season,
                    game_type_id=settings.game_type_id,
                    state="active" if skater_season_rows else "scheduled",
                ))
            else:
                season.state = "active" if skater_season_rows else "scheduled"

        _finish_run(engine, run_id, status="succeeded", counts=counts)
        return counts
    except Exception as exc:
        _finish_run(engine, run_id, status="failed", error=str(exc))
        raise
