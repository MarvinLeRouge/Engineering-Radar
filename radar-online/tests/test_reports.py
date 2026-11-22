import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from radar_online.accounts import create_active_account
from radar_online.main import app
from radar_online.models import ApiKey, PublishedReport, PublishedRepository, User, UserStatus
from sqlmodel import select


def _payload(commit_sha="a" * 40, global_score=7.4, repo_slug="summit-stats", **overrides):
    payload = {
        "schema_version": 1,
        "repository": {"slug": repo_slug, "display_name": "Summit-Stats"},
        "commit_sha": commit_sha,
        "scored_at": "2026-11-05T14:20:00Z",
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
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def client(database_url, monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)
    return TestClient(app)


@pytest.fixture
def api_key(session):
    return create_active_account(session, email="ada@example.com", display_name="Ada", slug="ada")


def _post(client, key, payload):
    return client.post("/api/reports", json=payload, headers={"X-API-Key": key})


def test_first_upload_creates_the_repository_and_the_report(client, api_key, session):
    response = _post(client, api_key, _payload())

    assert response.status_code == 201
    assert response.json() == {"report_path": "/u/ada/summit-stats"}
    repository = session.exec(select(PublishedRepository)).one()
    report = session.exec(select(PublishedReport)).one()
    assert (repository.slug, repository.display_name) == ("summit-stats", "Summit-Stats")
    assert report.repository_id == repository.id
    assert report.commit_sha == "a" * 40
    assert report.scored_at == datetime(2026, 11, 5, 14, 20, tzinfo=UTC)
    assert report.methodology_version == "Quality Framework v1.0"
    assert (report.schema_version, report.global_score) == (1, 7.4)
    assert report.payload["categories"][0]["name"] == "Security"


def test_same_commit_replaces_its_report(client, api_key, session):
    _post(client, api_key, _payload(global_score=7.4))

    response = _post(client, api_key, _payload(global_score=8.1))

    assert response.status_code == 200
    report = session.exec(select(PublishedReport)).one()
    assert report.global_score == 8.1
    assert report.payload["global_score"] == 8.1


def test_another_commit_adds_a_report_to_the_same_repository(client, api_key, session):
    _post(client, api_key, _payload(commit_sha="a" * 40))

    response = _post(client, api_key, _payload(commit_sha="b" * 40))

    assert response.status_code == 201
    assert len(session.exec(select(PublishedRepository)).all()) == 1
    assert len(session.exec(select(PublishedReport)).all()) == 2


def test_display_name_follows_the_latest_upload(client, api_key, session):
    _post(client, api_key, _payload())

    _post(client, api_key, _payload(repository={"slug": "summit-stats", "display_name": "Summit"}))

    assert session.exec(select(PublishedRepository.display_name)).one() == "Summit"


def test_same_repository_slug_is_namespaced_per_user(client, api_key, session):
    other_key = create_active_account(
        session, email="bob@example.com", display_name="Bob", slug="bob"
    )

    _post(client, api_key, _payload())
    response = _post(client, other_key, _payload())

    assert response.json() == {"report_path": "/u/bob/summit-stats"}
    assert len(session.exec(select(PublishedRepository)).all()) == 2


def test_missing_key_is_rejected(client):
    response = client.post("/api/reports", json=_payload())

    assert response.status_code == 401


def test_unknown_key_is_rejected(client, api_key):
    assert _post(client, "not-a-real-key", _payload()).status_code == 401


def test_revoked_key_is_rejected(client, api_key, session):
    stored_key = session.exec(select(ApiKey)).one()
    stored_key.revoked_at = datetime.now(UTC)
    session.add(stored_key)
    session.commit()

    assert _post(client, api_key, _payload()).status_code == 401


def test_key_of_an_inactive_user_is_rejected(client, api_key, session):
    user = session.exec(select(User)).one()
    user.status = UserStatus.DISABLED
    session.add(user)
    session.commit()

    assert _post(client, api_key, _payload()).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"leaked": "finding"},
        {"global_score": 11},
        {"schema_version": 2},
        {"commit_sha": "not-a-sha"},
    ],
)
def test_invalid_payload_is_rejected_and_nothing_is_stored(client, api_key, session, overrides):
    response = _post(client, api_key, _payload(**overrides))

    assert response.status_code == 422
    assert session.exec(select(PublishedRepository)).all() == []


def test_body_over_64_kib_is_rejected(client, api_key, session):
    body = json.dumps(_payload(padding="x" * 65 * 1024))

    response = client.post(
        "/api/reports",
        content=body,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert session.exec(select(PublishedRepository)).all() == []
