import pytest
from radar_api.dependencies import get_db_session
from sqlmodel import Session


def test_get_db_session_yields_a_session_and_closes_it(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{db_path}")

    generator = get_db_session()
    session = next(generator)
    assert isinstance(session, Session)

    with pytest.raises(StopIteration):
        next(generator)
