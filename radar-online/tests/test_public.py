import pytest
from fastapi.testclient import TestClient
from radar_online.accounts import create_active_account
from radar_online.main import app
from radar_online.models import User, UserStatus
from sqlmodel import select

_CACHE = "public, max-age=300"


def _payload(commit_sha, scored_at, global_score, repo_slug="summit-stats"):
    return {
        "schema_version": 1,
        "repository": {"slug": repo_slug, "display_name": "Summit-Stats"},
        "commit_sha": commit_sha,
        "scored_at": scored_at,
        "methodology_version": "Quality Framework v1.0",
        "global_score": global_score,
        "categories": [
            {
                "name": "Security",
                "order": 4,
                "weight": 1.5,
                "status": "scored",
                "implemented": True,
                "value": global_score,
                "confidence": "HIGH",
            },
            {
                "name": "Performance",
                "order": 6,
                "weight": 1.0,
                "status": "not_yet_audited",
                "implemented": False,
                "value": None,
                "confidence": None,
            },
        ],
    }


@pytest.fixture
def client(database_url, monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)
    return TestClient(app)


@pytest.fixture
def api_key(session):
    return create_active_account(session, email="ada@example.com", display_name="Ada", slug="ada")


def _upload(client, key, payload):
    response = client.post("/api/reports", json=payload, headers={"X-API-Key": key})
    assert response.status_code in (200, 201)


@pytest.fixture
def published(client, api_key):
    # Uploaded out of order: the newer commit first, so "latest" must follow scored_at.
    _upload(client, api_key, _payload("b" * 40, "2026-11-10T10:00:00Z", 8.1))
    _upload(client, api_key, _payload("a" * 40, "2026-11-05T10:00:00Z", 7.4))
    return api_key


def test_profile_lists_repositories_with_their_latest_score(client, published):
    response = client.get("/api/users/ada")

    assert response.status_code == 200
    assert response.headers["cache-control"] == _CACHE
    assert response.json() == {
        "slug": "ada",
        "display_name": "Ada",
        "repositories": [
            {
                "slug": "summit-stats",
                "display_name": "Summit-Stats",
                "latest_global_score": 8.1,
                "latest_scored_at": "2026-11-10T10:00:00Z",
            }
        ],
    }
    assert "email" not in response.text


def test_unknown_user_is_not_found(client):
    assert client.get("/api/users/nobody").status_code == 404


def test_inactive_user_is_hidden(client, published, session):
    user = session.exec(select(User)).one()
    user.status = UserStatus.DISABLED
    session.add(user)
    session.commit()

    assert client.get("/api/users/ada").status_code == 404
    assert client.get("/api/users/ada/repositories/summit-stats/report").status_code == 404


def test_report_is_the_latest_scored_commit(client, published):
    response = client.get("/api/users/ada/repositories/summit-stats/report")

    assert response.status_code == 200
    assert response.headers["cache-control"] == _CACHE
    body = response.json()
    assert body["user"] == {"slug": "ada", "display_name": "Ada"}
    assert body["repository"] == {"slug": "summit-stats", "display_name": "Summit-Stats"}
    assert body["report"]["commit_sha"] == "b" * 40
    assert body["report"]["global_score"] == 8.1
    assert "uploaded_at" in body


def test_unknown_repository_report_is_not_found(client, published):
    assert client.get("/api/users/ada/repositories/other/report").status_code == 404


def test_history_has_one_point_per_commit_oldest_first(client, published):
    response = client.get("/api/users/ada/repositories/summit-stats/history")

    assert response.status_code == 200
    assert response.headers["cache-control"] == _CACHE
    assert response.json() == [
        {
            "commit_sha": "a" * 40,
            "scored_at": "2026-11-05T10:00:00Z",
            "global_score": 7.4,
            "categories": [
                {"name": "Security", "order": 4, "value": 7.4, "implemented": True},
                {"name": "Performance", "order": 6, "value": None, "implemented": False},
            ],
        },
        {
            "commit_sha": "b" * 40,
            "scored_at": "2026-11-10T10:00:00Z",
            "global_score": 8.1,
            "categories": [
                {"name": "Security", "order": 4, "value": 8.1, "implemented": True},
                {"name": "Performance", "order": 6, "value": None, "implemented": False},
            ],
        },
    ]


def test_history_of_an_unknown_repository_is_not_found(client, published):
    assert client.get("/api/users/ada/repositories/other/history").status_code == 404


def test_badge_shows_the_latest_score_marked_self_assessed(client, published):
    response = client.get("/api/users/ada/repositories/summit-stats/badge")

    assert response.status_code == 200
    assert response.headers["cache-control"] == _CACHE
    assert response.json() == {
        "schemaVersion": 1,
        "label": "quality",
        "message": "8.1/10 (self-assessed)",
        "color": "brightgreen",
    }


@pytest.mark.parametrize(
    "path",
    [
        "/api/users/nobody/repositories/summit-stats/badge",
        "/api/users/ada/repositories/other/badge",
    ],
)
def test_badge_is_grey_when_nothing_is_published(client, published, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.json()["message"] == "not published"
    assert response.json()["color"] == "lightgrey"


def test_badge_without_a_global_score_is_grey(client, api_key):
    payload = _payload("a" * 40, "2026-11-05T10:00:00Z", None)
    _upload(client, api_key, payload)

    response = client.get("/api/users/ada/repositories/summit-stats/badge")

    assert response.json()["message"] == "not published"
