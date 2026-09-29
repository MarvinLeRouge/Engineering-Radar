import pytest
from radar_api.config import (
    MissingApiKeyError,
    MissingDatabaseUrlError,
    get_api_key,
    get_database_url,
)


def test_get_database_url_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADAR_DATABASE_URL", raising=False)
    with pytest.raises(MissingDatabaseUrlError):
        get_database_url()


def test_get_database_url_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_DATABASE_URL", "sqlite:///test.db")
    assert get_database_url() == "sqlite:///test.db"


def test_get_api_key_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADAR_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        get_api_key()


def test_get_api_key_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    assert get_api_key() == "secret"
