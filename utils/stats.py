"""Shared pagination and coercion helpers for NHL Stats REST reports."""

from collections.abc import Mapping
from typing import Any

from .http import get_json


def _int(value: Any) -> int | None:
    return None if value is None or value == "" else int(value)


def _float(value: Any) -> float | None:
    return None if value is None or value == "" else float(value)


def fetch_report(client: Any, report: str, *, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Fetch a complete Stats REST report, with safe 100-row fallback paging."""
    first_params = dict(params)
    first_params.update(limit=-1, start=0)
    payload = get_json(client, f"/stats/rest/en/{report}", first_params)
    rows = list(payload.get("data") or [])
    total = int(payload.get("total", len(rows)))
    if len(rows) == total:
        return rows

    page_size = 100
    rows = []
    start = 0
    while start < total:
        page_params = dict(params, limit=page_size, start=start)
        page = get_json(client, f"/stats/rest/en/{report}", page_params)
        page_rows = list(page.get("data") or [])
        if not page_rows:
            raise ValueError(f"empty page at start={start} while fetching {report}")
        rows.extend(page_rows)
        start += len(page_rows)
    if len(rows) != total:
        raise ValueError(f"{report}: expected {total} rows, received {len(rows)}")
    return rows


def season_params(season_id: int, game_type_id: int = 2) -> dict[str, Any]:
    return {
        "cayenneExp": f"seasonId={season_id} and gameTypeId={game_type_id}",
        "sort": [{"property": "teamId", "direction": "ASC"}],
    }


__all__ = ["fetch_report", "season_params", "_int", "_float"]
