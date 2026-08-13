import pytest

from config import Settings
from ingestion.seasons import SeasonValidationError, generate_season_ids, validate_season_coverage


def test_generate_season_ids_is_inclusive_and_gap_free():
    assert generate_season_ids(20222023, 20262027) == (
        20222023,
        20232024,
        20242025,
        20252026,
        20262027,
    )


def test_generation_rejects_invalid_season_id():
    with pytest.raises(SeasonValidationError):
        generate_season_ids(20222024, 20232024)


def test_discovery_rejects_missing_intermediate_season():
    with pytest.raises(SeasonValidationError, match="20232024"):
        validate_season_coverage(
            generate_season_ids(20222023, 20262027),
            [20222023, 20242025, 20252026, 20262027],
        )


def test_discovery_ignores_newer_api_seasons_but_returns_configured_range():
    expected = generate_season_ids(20222023, 20262027)
    assert validate_season_coverage(expected, [*expected, 20272028]) == expected


def test_settings_exposes_all_configured_seasons():
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    assert settings.season_ids == generate_season_ids(20222023, 20262027)


def test_settings_rejects_reverse_range():
    with pytest.raises(ValueError, match="backfill_through_season_id"):
        Settings(
            _env_file=None,
            backfill_start_season_id=20242025,
            backfill_through_season_id=20232024,
        )
