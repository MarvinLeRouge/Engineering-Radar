import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from radar_online.dependencies import get_db_session
from sqlmodel import text

RADAR_ONLINE_ROOT = Path(__file__).resolve().parents[1]


def _tables(database_url: str) -> set[str]:
    path = database_url.removeprefix("sqlite:///")
    query = "select name from sqlite_master where type='table'"
    return {row[0] for row in sqlite3.connect(path).execute(query)}


def test_migrations_upgrade_an_empty_database_to_head(database_url: str) -> None:
    assert "alembic_version" in _tables(database_url)


def test_migrations_never_create_the_local_radar_tables(database_url: str) -> None:
    # radar-online must not host radar-core's audit data (ADR 0014).
    local_tables = {"finding", "audit", "repository", "scoring_run", "tool_result"}

    assert not _tables(database_url) & local_tables


def test_migrations_refuse_a_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADAR_ONLINE_DATABASE_URL", raising=False)
    config = Config(str(RADAR_ONLINE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(RADAR_ONLINE_ROOT / "alembic"))

    with pytest.raises(RuntimeError, match="RADAR_ONLINE_DATABASE_URL"):
        command.upgrade(config, "head")


def test_db_session_is_bound_to_the_configured_database(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)
    sessions = get_db_session()

    session = next(sessions)

    assert session.exec(text("select 1")).one() == (1,)
    sessions.close()


def test_alembic_metadata_holds_no_local_radar_table() -> None:
    # Guards autogenerate: SQLModel.metadata is shared, so importing radar_core.models
    # anywhere radar-online loads would put the local audit tables in its migrations.
    import sys

    import radar_online.main  # noqa: F401
    import radar_online.models  # noqa: F401
    from sqlmodel import SQLModel

    assert "radar_core.models" not in sys.modules
    assert not set(SQLModel.metadata.tables) & {"finding", "audit", "repository", "scoring_run"}
