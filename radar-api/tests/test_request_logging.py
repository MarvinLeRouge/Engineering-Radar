from fastapi import FastAPI
from fastapi.testclient import TestClient
from radar_api.request_logging import log_requests
from structlog.testing import capture_logs


def test_logs_one_line_per_request_with_route_status_and_duration(client):
    with capture_logs() as logs:
        client.get("/repositories?secret=should-not-appear", headers={"X-API-Key": "key"})

    [entry] = [log for log in logs if log["event"] == "request_handled"]
    assert entry["method"] == "GET"
    assert entry["path"] == "/repositories"
    assert entry["status"] == 200
    assert entry["log_level"] == "info"
    assert isinstance(entry["duration_ms"], int)
    # Query strings and headers (the API key) are never logged.
    assert "should-not-appear" not in str(entry)
    assert set(entry) == {"event", "log_level", "method", "path", "status", "duration_ms"}


def test_logs_server_errors_at_error_level():
    failing_app = FastAPI()
    failing_app.middleware("http")(log_requests)

    @failing_app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with capture_logs() as logs:
        TestClient(failing_app, raise_server_exceptions=False).get("/boom")

    [entry] = [log for log in logs if log["event"] == "request_handled"]
    assert entry["status"] == 500
    assert entry["log_level"] == "error"


def test_logs_client_errors_at_info_level(client):
    with capture_logs() as logs:
        client.get("/no-such-route")

    [entry] = [log for log in logs if log["event"] == "request_handled"]
    assert entry["status"] == 404
    assert entry["log_level"] == "info"
