from fastapi.testclient import TestClient
from radar_online.main import app


def test_health_answers_under_the_api_prefix() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_docs_are_served_under_the_api_prefix() -> None:
    assert TestClient(app).get("/api/openapi.json").status_code == 200
