"""Database session dependency for radar-api route handlers."""

from __future__ import annotations

from collections.abc import Generator

from radar_core.db import get_engine, get_session
from sqlmodel import Session

from radar_api.config import get_database_url


def get_db_session() -> Generator[Session, None, None]:
    """Yield a session bound to RADAR_DATABASE_URL and dispose its engine when the request ends."""
    engine = get_engine(get_database_url())
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
