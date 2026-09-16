"""Engine and session handling."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from sabi.config import settings

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings().database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            future=True,
        )
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _Session


@contextmanager
def session_scope() -> Iterator[Session]:
    s = session_factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s


def reset_engine() -> None:
    """Test hook -- drop cached engine so a new DATABASE_URL takes effect."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def ping() -> bool:
    try:
        with engine().connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False
