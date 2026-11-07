import pytest
from radar_online.config import MissingDatabaseUrlError, get_database_url


def test_get_database_url_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADAR_ONLINE_DATABASE_URL", raising=False)

    with pytest.raises(MissingDatabaseUrlError):
        get_database_url()


def test_get_database_url_raises_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", "")

    with pytest.raises(MissingDatabaseUrlError):
        get_database_url()


def test_get_database_url_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", "sqlite:///x.db")

    assert get_database_url() == "sqlite:///x.db"
