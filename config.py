"""Configuration shared by ingestion, API, and scheduled refresh jobs."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingestion.seasons import generate_season_ids


class Settings(BaseSettings):
    """Environment-backed application settings.

    The bounds are inclusive.  The season generator intentionally expands the
    whole range so a newly added season can never create a silent historical
    gap.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    seed_csv_path: Path = Path("data/data_dump.csv")
    backfill_start_season_id: int = 20222023
    backfill_through_season_id: int = 20262027
    game_type_id: int = 2
    daily_correction_lookback_days: int = 3
    daily_max_recovery_days: int = 14
    daily_timezone: str = "America/New_York"
    database_url: str = "sqlite:///./nhl.db"
    request_timeout_seconds: float = 30.0
    request_max_retries: int = 3

    @field_validator("backfill_start_season_id", "backfill_through_season_id")
    @classmethod
    def validate_season_id(cls, value: int) -> int:
        # The NHL encodes a season as YYYYZZZZ, where ZZZZ is YYYY + 1.
        text = str(value)
        if len(text) != 8 or not text.isdigit() or int(text[4:]) != int(text[:4]) + 1:
            raise ValueError(f"invalid NHL season id: {value!r}")
        return value

    @field_validator("backfill_through_season_id")
    @classmethod
    def validate_range(cls, value: int, info) -> int:
        start = info.data.get("backfill_start_season_id")
        if start is not None and value < start:
            raise ValueError("backfill_through_season_id must be >= backfill_start_season_id")
        return value

    @field_validator("game_type_id")
    @classmethod
    def validate_game_type(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("game_type_id must be positive")
        return value

    @field_validator("daily_correction_lookback_days", "daily_max_recovery_days")
    @classmethod
    def validate_lookback(cls, value: int) -> int:
        if value < 1:
            raise ValueError("daily refresh windows must be at least 1 day")
        return value

    @field_validator("daily_max_recovery_days")
    @classmethod
    def validate_recovery_window(cls, value: int, info) -> int:
        lookback = info.data.get("daily_correction_lookback_days")
        if lookback is not None and value < lookback:
            raise ValueError(
                "daily_max_recovery_days must be >= daily_correction_lookback_days"
            )
        return value

    @property
    def season_ids(self) -> tuple[int, ...]:
        """Every configured season, including both endpoints."""

        return generate_season_ids(
            self.backfill_start_season_id,
            self.backfill_through_season_id,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings object."""

    return Settings()
