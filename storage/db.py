"""SQLAlchemy engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import Settings, get_settings
from .models import Base


def make_engine(settings: Settings | None = None) -> Engine:
    """Create an engine without opening a connection until first use."""

    current = settings or get_settings()
    kwargs = {"pool_pre_ping": True}
    if current.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(current.database_url, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a transaction-scoped session for scripts and tests."""

    factory = create_session_factory(engine)
    with factory.begin() as session:
        yield session
