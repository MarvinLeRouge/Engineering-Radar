import pytest
from fastapi import HTTPException
from radar_api.auth import require_api_key


def test_require_api_key_raises_when_missing(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None)

    assert exc_info.value.status_code == 401


def test_require_api_key_raises_when_wrong(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong")

    assert exc_info.value.status_code == 401


def test_require_api_key_passes_when_correct(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    require_api_key(x_api_key="secret")
