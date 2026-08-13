"""Position-preserving importer for the supplied NHL seed CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SeedSkaterRow:
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
    blank_1: str | None
    shots: int
    shooting_pct: float | None
    seconds_per_game: float | None
    minutes_per_game: float | None
    blank_2: str | None
    shifts_per_game: float | None
    faceoff_pct: float | None
    season_id: int
    ppp: int
    shp: int
    raw_values: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__ if field != "raw_values"}


def load_seed_csv(path: str | Path, *, expected_season_id: int = 20222023) -> list[SeedSkaterRow]:
    """Load rows without collapsing the two positional blank columns."""
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or len(header) != 24:
            raise ValueError(f"expected a 24-column NHL seed header, got {len(header or [])}")
        if header[0:3] != ["playerId", "Name", "Team"] or header[13] != "" or header[18] != "":
            raise ValueError("unexpected seed CSV column order; blank columns are positional")
        rows: list[SeedSkaterRow] = []
        seen: set[tuple[int, int]] = set()
        for line_no, values in enumerate(reader, start=2):
            if not any(values):
                continue
            if len(values) != 24:
                raise ValueError(f"line {line_no}: expected 24 columns, got {len(values)}")
            season_id = int(values[21])
            if season_id != expected_season_id:
                raise ValueError(f"line {line_no}: expected season {expected_season_id}, got {season_id}")
            player_id = int(values[0])
            key = (season_id, player_id)
            if key in seen:
                raise ValueError(f"line {line_no}: duplicate player-season {key}")
            seen.add(key)
            rows.append(SeedSkaterRow(
                player_id=player_id, name=values[1].strip(), team=_text(values[2]), position=_text(values[3]),
                games_played=_int(values[4]), goals=_int(values[5]), assists=_int(values[6]), points=_int(values[7]),
                plus_minus=_int(values[8]), pim=_int(values[9]), ppg=_int(values[10]), shg=_int(values[11]),
                gwg=_int(values[12]), blank_1=_text(values[13]), shots=_int(values[14]), shooting_pct=_float(values[15]),
                seconds_per_game=_float(values[16]), minutes_per_game=_float(values[17]), blank_2=_text(values[18]),
                shifts_per_game=_float(values[19]), faceoff_pct=_float(values[20]), season_id=season_id,
                ppp=_int(values[22]), shp=_int(values[23]), raw_values=tuple(values),
            ))
    return rows


def _text(value: str) -> str | None:
    value = value.strip()
    return None if not value or value.lower() == "none" else value


def _int(value: str) -> int:
    return int(value) if value.strip() else 0


def _float(value: str) -> float | None:
    value = value.strip()
    return None if not value or value.lower() == "none" else float(value)
