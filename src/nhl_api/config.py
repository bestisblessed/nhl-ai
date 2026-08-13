from __future__ import annotations

import os

DEFAULT_DATABASE_URL = "postgresql+psycopg://nhl:nhl@localhost:5432/nhl"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
