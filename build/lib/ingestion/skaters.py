"""NHL Stats REST skater season and game ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .client import NHLHTTPClient
from .records import PlayerGameRecord


SUMMARY_FIELDS = (
    "assists", "evGoals", "evPoints", "faceoffWinPct", "gameWinningGoals", "gamesPlayed",
    "goals", "lastName", "otGoals", "penaltyMinutes", "playerId", "plusMinus", "points",
    "pointsPerGame", "positionCode", "ppGoals", "ppPoints", "seasonId", "shGoals", "shPoints",
    "shootingPct", "shootsCatches", "shots", "skaterFullName", "teamAbbrevs", "timeOnIcePerGame",
)
TOI_FIELDS = (
    "evTimeOnIce", "evTimeOnIcePerGame", "gamesPlayed", "otTimeOnIce", "otTimeOnIcePerOtGame",
    "playerId", "positionCode", "ppTimeOnIce", "ppTimeOnIcePerGame", "shTimeOnIce", "shTimeOnIcePerGame",
    "shifts", "shiftsPerGame", "seasonId", "shootsCatches", "skaterFullName", "teamAbbrevs",
    "timeOnIce", "timeOnIcePerGame", "timeOnIcePerShift",
)


@dataclass(frozen=True)
class SkaterSeasonRow:
    player_id: int
    name: str
    team: str | None
    position: str | None
    games_played: int
    goals: int
    assists: int
    points: int
    plus_minus: int
    pim: int
    ppg: int
    shg: int
    gwg: int
    shots: int
    shooting_pct: float | None
    seconds_per_game: float | None
    minutes_per_game: float | None
    shifts_per_game: float | None
    faceoff_pct: float | None
    ppp: int
    shp: int
    season_id: int
    raw_summary: dict[str, Any]
    raw_time_on_ice: dict[str, Any] | None = None

    def as_dict(self, *, game_type_id: int = 2) -> dict[str, Any]:
        """Return persistence-friendly names while retaining source IDs."""
        return {
            "player_id": self.player_id,
            "season_id": self.season_id,
            "game_type_id": game_type_id,
            "name": self.name,
            "team_abbrev": self.team,
            "position": self.position,
            "games_played": self.games_played,
            "goals": self.goals,
            "assists": self.assists,
            "points": self.points,
            "plus_minus": self.plus_minus,
            "pim": self.pim,
            "ppg": self.ppg,
            "shg": self.shg,
            "gwg": self.gwg,
            "shots": self.shots,
            "shooting_pct": self.shooting_pct,
            "toi_seconds": self.seconds_per_game,
            "minutes_per_game": self.minutes_per_game,
            "shifts_per_game": self.shifts_per_game,
            "faceoff_pct": self.faceoff_pct,
            "ppp": self.ppp,
            "shp": self.shp,
        }


class SkaterStatsIngestor:
    """Fetch, paginate, and normalize skater reports."""

    def __init__(self, client: NHLHTTPClient, *, page_size: int = 100):
        self.client = client
        self.page_size = max(1, page_size)

    def fetch_season_summary(self, season_id: int, *, game_type_id: int = 2) -> list[dict[str, Any]]:
        return self._fetch_report("skater/summary", season_id, game_type_id=game_type_id, is_game=False)

    def fetch_season_time_on_ice(self, season_id: int, *, game_type_id: int = 2) -> list[dict[str, Any]]:
        return self._fetch_report("skater/timeonice", season_id, game_type_id=game_type_id, is_game=False)

    def fetch_game_summary(self, season_id: int, *, game_date: str | None = None, game_type_id: int = 2) -> list[dict[str, Any]]:
        extra = f' and gameDate="{game_date}"' if game_date else ""
        return self._fetch_report(
            "skater/summary", season_id, game_type_id=game_type_id, is_game=True, extra=extra,
            sort=[{"property": "gameId", "direction": "ASC"}, {"property": "playerId", "direction": "ASC"}],
        )

    def normalize_games(
        self,
        summary: Iterable[dict[str, Any]],
        *,
        team_ids_by_abbrev: dict[str, int],
        game_type_id: int = 2,
    ) -> list[PlayerGameRecord]:
        """Normalize ``isGame=true`` summary rows for transactional upserts."""
        rows: list[PlayerGameRecord] = []
        for item in summary:
            self._validate_game_summary(item)
            team_abbrev = str(item["teamAbbrev"]).strip().upper()
            try:
                team_id = team_ids_by_abbrev[team_abbrev]
            except KeyError as exc:
                raise ValueError(f"unknown team abbreviation in skater game summary: {team_abbrev}") from exc
            rows.append(PlayerGameRecord(
                game_id=int(item["gameId"]),
                player_id=int(item["playerId"]),
                player_name=str(item.get("skaterFullName") or "").strip(),
                team_id=team_id,
                team_abbrev=team_abbrev,
                position_code=self._text(item.get("positionCode")),
                game_type_id=int(game_type_id),
                goals=self._int(item.get("goals")),
                assists=self._int(item.get("assists")),
                points=self._int(item.get("points")),
                pim=self._int(item.get("penaltyMinutes")),
                shots=self._int(item.get("shots")),
                # The game-level report retains the aggregate field name, but
                # with one game this value is the player's exact game TOI.
                toi_seconds=self._float(item.get("timeOnIcePerGame")),
            ))
        return rows

    def normalize_season(self, summary: Iterable[dict[str, Any]], time_on_ice: Iterable[dict[str, Any]] = ()) -> list[SkaterSeasonRow]:
        toi_by_player = {int(r["playerId"]): r for r in time_on_ice if r.get("playerId") is not None}
        rows: list[SkaterSeasonRow] = []
        for item in summary:
            self._validate_summary(item)
            pid = int(item["playerId"])
            toi = toi_by_player.get(pid, {})
            seconds = toi.get("timeOnIcePerGame", item.get("timeOnIcePerGame"))
            rows.append(SkaterSeasonRow(
                player_id=pid, name=str(item.get("skaterFullName") or "").strip(),
                team=self._text(item.get("teamAbbrevs")), position=self._text(item.get("positionCode")),
                games_played=self._int(item.get("gamesPlayed")), goals=self._int(item.get("goals")),
                assists=self._int(item.get("assists")), points=self._int(item.get("points")),
                plus_minus=self._int(item.get("plusMinus")), pim=self._int(item.get("penaltyMinutes")),
                ppg=self._int(item.get("ppGoals")), shg=self._int(item.get("shGoals")),
                gwg=self._int(item.get("gameWinningGoals")), shots=self._int(item.get("shots")),
                shooting_pct=self._float(item.get("shootingPct")), seconds_per_game=self._float(seconds),
                minutes_per_game=self._float(seconds, divisor=60), shifts_per_game=self._float(toi.get("shiftsPerGame")),
                faceoff_pct=self._float(item.get("faceoffWinPct")), ppp=self._int(item.get("ppPoints")),
                shp=self._int(item.get("shPoints")), season_id=self._int(item.get("seasonId")),
                raw_summary=dict(item), raw_time_on_ice=dict(toi) if toi else None,
            ))
        return rows

    def _fetch_report(
        self, report: str, season_id: int, *, game_type_id: int, is_game: bool,
        extra: str = "", sort: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        expression = f"seasonId={int(season_id)} and gameTypeId={int(game_type_id)}{extra}"
        rows: list[dict[str, Any]] = []
        start = 0
        expected_total: int | None = None
        while True:
            payload, _ = self.client.get_json(report, {
                "isAggregate": "false", "isGame": str(is_game).lower(), "cayenneExp": expression,
                "sort": sort or [{"property": "playerId", "direction": "ASC"}],
                "start": start, "limit": self.page_size,
            })
            page = payload.get("data")
            if not isinstance(page, list):
                raise ValueError(f"NHL report {report} has no data array")
            total = payload.get("total")
            if total is not None and expected_total is None:
                expected_total = int(total)
            rows.extend(r for r in page if isinstance(r, dict))
            if not page or (expected_total is not None and len(rows) >= expected_total):
                break
            start += len(page)
        if expected_total is not None and len(rows) != expected_total:
            raise ValueError(f"NHL report {report} incomplete: expected {expected_total}, received {len(rows)}")
        return rows

    @staticmethod
    def _validate_summary(item: dict[str, Any]) -> None:
        for field in ("playerId", "seasonId", "gamesPlayed", "goals", "assists", "points"):
            if field not in item:
                raise ValueError(f"skater summary missing required field {field}")

    @staticmethod
    def _validate_game_summary(item: dict[str, Any]) -> None:
        for field in ("gameId", "playerId", "teamAbbrev", "goals", "assists", "points"):
            if field not in item:
                raise ValueError(f"skater game summary missing required field {field}")

    @staticmethod
    def _int(value: Any) -> int:
        return int(value or 0)

    @staticmethod
    def _float(value: Any, divisor: float = 1) -> float | None:
        if value is None or value == "None" or value == "":
            return None
        return float(value) / divisor

    @staticmethod
    def _text(value: Any) -> str | None:
        value = str(value).strip() if value is not None else ""
        return value or None
