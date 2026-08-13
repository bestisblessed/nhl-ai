"""Gap-free NHL season range generation and API discovery validation."""

from collections.abc import Iterable, Mapping


class SeasonValidationError(ValueError):
    """Raised when the configured or discovered season range is invalid."""


def _season_start_year(season_id: int | str) -> int:
    text = str(season_id)
    if len(text) != 8 or not text.isdigit():
        raise SeasonValidationError(f"invalid NHL season id: {season_id!r}")
    start_year, end_year = int(text[:4]), int(text[4:])
    if end_year != start_year + 1:
        raise SeasonValidationError(f"invalid NHL season id: {season_id!r}")
    return start_year


def generate_season_ids(start: int | str, through: int | str) -> tuple[int, ...]:
    """Generate all contiguous season IDs in an inclusive range."""

    first = _season_start_year(start)
    last = _season_start_year(through)
    if last < first:
        raise SeasonValidationError("season range ends before it starts")
    return tuple(year * 10000 + year + 1 for year in range(first, last + 1))


def _coerce_discovered(value: int | str | Mapping[str, object]) -> int:
    if isinstance(value, Mapping):
        value = value.get("id", value.get("seasonId", value.get("season_id", "")))
    return int(value)


def validate_season_coverage(
    expected_seasons: Iterable[int | str],
    discovered_seasons: Iterable[int | str | Mapping[str, object]],
) -> tuple[int, ...]:
    """Validate that an API response contains every expected season.

    Returns the sorted discovered values restricted to the expected range.  A
    missing season is an error; extra API seasons are harmless and ignored.
    """

    expected = tuple(int(value) for value in expected_seasons)
    if not expected:
        raise SeasonValidationError("expected season range cannot be empty")
    if len(set(expected)) != len(expected):
        raise SeasonValidationError("expected season range contains duplicates")
    # Validate each expected ID and its ordering before comparing API values.
    generated = generate_season_ids(min(expected), max(expected))
    if expected != generated:
        raise SeasonValidationError(
            "expected seasons must be contiguous and ordered: "
            f"{expected!r} != {generated!r}"
        )

    discovered = {_coerce_discovered(value) for value in discovered_seasons}
    missing = [season for season in expected if season not in discovered]
    if missing:
        raise SeasonValidationError(
            "NHL season discovery is missing configured seasons: "
            + ", ".join(str(season) for season in missing)
        )
    return tuple(season for season in generated if season in discovered)
