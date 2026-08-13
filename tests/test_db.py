from storage.db import normalize_database_url


def test_postgresql_urls_use_psycopg_driver_without_opening_connection():
    assert normalize_database_url("postgresql://user:pass@db.example/nhl") == (
        "postgresql+psycopg://user:pass@db.example/nhl"
    )
