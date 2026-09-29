from __future__ import annotations

from collections.abc import Generator

from radar_core.db import get_engine, get_session
from sqlmodel import Session

from radar_api.config import get_database_url


def get_db_session() -> Generator[Session, None, None]:
    engine = get_engine(get_database_url())
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
