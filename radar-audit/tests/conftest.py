import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from alembic import command
from alembic.config import Config
from radar_core.db import get_engine
from sqlmodel import Session

RADAR_CORE_ROOT = Path(__file__).resolve().parents[2] / "radar-core"
ALEMBIC_INI = RADAR_CORE_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = RADAR_CORE_ROOT / "alembic"

ToolResponder = Callable[[list[str], Path | None], subprocess.CompletedProcess[str] | None]


def _run_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    previous_url = os.environ.get("RADAR_DATABASE_URL")
    os.environ["RADAR_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_url is None:
            del os.environ["RADAR_DATABASE_URL"]
        else:
            os.environ["RADAR_DATABASE_URL"] = previous_url


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    _run_migrations(database_url)

    engine = get_engine(database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def fake_tool(monkeypatch):
    """Replace a runner module's tool calls with a canned result; return the recorded commands.

    Patches `run_timed` on the runner module when it imports it, else `subprocess.run` (the
    PHP scratch-project runners call it directly). `respond(command, cwd)` can write the
    report files a tool would produce and can return its own result for that call; returning
    None falls back to the canned stdout/stderr/returncode.
    """

    def install(
        module: ModuleType,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        respond: ToolResponder | None = None,
    ) -> list[list[str]]:
        calls: list[list[str]] = []

        def call(command: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
            calls.append(list(command))
            result = respond(list(command), cwd) if respond else None
            if result is not None:
                return result
            return subprocess.CompletedProcess(command, returncode, stdout, stderr)

        if hasattr(module, "run_timed"):
            monkeypatch.setattr(
                module, "run_timed", lambda command, timeout_s, cwd=None: (call(command, cwd), 1)
            )
        else:
            # module.subprocess is the global module: set up git repos before installing the fake.
            monkeypatch.setattr(
                module.subprocess, "run", lambda command, **kwargs: call(command, kwargs.get("cwd"))
            )
        return calls

    return install
