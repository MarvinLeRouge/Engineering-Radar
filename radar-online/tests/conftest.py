import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

RADAR_ONLINE_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = RADAR_ONLINE_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = RADAR_ONLINE_ROOT / "alembic"


def run_migrations(database_url: str) -> None:
    """Upgrade the database at `database_url` to radar-online's latest migration."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    previous_url = os.environ.get("RADAR_ONLINE_DATABASE_URL")
    os.environ["RADAR_ONLINE_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_url is None:
            del os.environ["RADAR_ONLINE_DATABASE_URL"]
        else:
            os.environ["RADAR_ONLINE_DATABASE_URL"] = previous_url


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """A migrated, throwaway SQLite database, never the real one."""
    url = f"sqlite:///{tmp_path / 'radar-online.db'}"
    run_migrations(url)
    return url


@pytest.fixture
def session(database_url: str):
    """A session on the migrated throwaway database."""
    from radar_core.db import get_engine
    from sqlmodel import Session

    engine = get_engine(database_url)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()
