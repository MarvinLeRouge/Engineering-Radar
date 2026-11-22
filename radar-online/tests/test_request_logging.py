from fastapi import FastAPI
from fastapi.testclient import TestClient
from radar_core.request_logging import log_requests
from radar_online.main import app
from structlog.testing import capture_logs

_SECRET = "very-secret-token-value"


def _request_lines(logs):
    return [log for log in logs if log["event"] == "request_handled"]


def test_radar_online_logs_each_request_by_route_template(database_url, monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)

    with capture_logs() as logs:
        TestClient(app).get("/api/users/someone?q=1")

    [entry] = _request_lines(logs)
    assert entry["path"] == "/api/users/{user_slug}"
    assert entry["status"] == 404
    assert "someone" not in str(entry)


def test_a_token_in_a_path_and_the_api_key_never_reach_the_logs():
    token_app = FastAPI()
    token_app.middleware("http")(log_requests)

    @token_app.get("/api/reviews/{token}")
    def review(token: str) -> dict[str, str]:
        return {}

    with capture_logs() as logs:
        TestClient(token_app).get(f"/api/reviews/{_SECRET}", headers={"X-API-Key": _SECRET})

    [entry] = _request_lines(logs)
    assert entry["path"] == "/api/reviews/{token}"
    assert _SECRET not in str(logs)
