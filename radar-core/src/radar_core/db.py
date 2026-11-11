"""Database engine and session factories, enforcing SQLite foreign keys on every connection."""

import sqlite3
from typing import Protocol

from sqlalchemy import Engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import Session, create_engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(
    dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
) -> None:
    """Enforce foreign-key constraints on every new SQLite connection.

    SQLite disables FK enforcement by default for backward compatibility, so
    without this pragma a row referencing a nonexistent parent row inserts
    silently instead of raising `IntegrityError`. No-op for non-SQLite
    connections (e.g. a future Postgres backend), which enforce FKs natively.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine(database_url: str) -> Engine:
    """Create a SQLModel engine for the given database URL."""
    return create_engine(database_url)


def get_session(engine: Engine) -> Session:
    """Open a new SQLModel session bound to the given engine."""
    return Session(engine)


class _HasId(Protocol):
    @property
    def id(self) -> int | None: ...


def persisted_id(row: _HasId) -> int:
    """Return the primary key of a row already flushed to the database.

    Table models type `id` as `int | None` (unset until the first flush) while
    foreign-key fields expect `int`. Raises `ValueError` if the row was never flushed.
    """
    if row.id is None:
        raise ValueError(f"{type(row).__name__} has no id yet: flush it first")
    return row.id
