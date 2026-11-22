import io
import json
from urllib.error import HTTPError, URLError

import pytest
from radar_core import publishing
from radar_core.enums import Confidence, ScoreLevel, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from radar_core.publication_builder import build_publication_payload
from radar_core.publishing import (
    DirtyAuditError,
    PublishFailedError,
    PublishingNotConfiguredError,
    publish_scoring_run,
)

_KEY = "online-secret-key"


def _add(session, row):
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def make_scoring_run(session, is_dirty=False):
    repository = _add(session, Repository(name="Summit-Stats", path="/tmp/summit-stats"))
    audit = _add(
        session, Audit(repository_id=repository.id, commit_sha="e" * 40, is_dirty=is_dirty)
    )
    version = _add(session, MethodologyVersion(version_label="Quality Framework v1.0"))
    run = _add(
        session, ScoringRun(audit_id=audit.id, methodology_version_id=version.id, global_score=6.0)
    )
    category = _add(
        session, Category(methodology_version_id=version.id, name="Security", weight=1.0, order=4)
    )
    _add(
        session,
        Criterion(
            category_id=category.id,
            name="Dependency vulns",
            description="...",
            weight=1.0,
            scoring_model=ScoringModel.FIXED_SCALE,
            implemented=True,
        ),
    )
    _add(
        session,
        Score(
            scoring_run_id=run.id,
            category_id=category.id,
            level=ScoreLevel.CATEGORY,
            value=6.0,
            confidence=Confidence.HIGH,
        ),
    )
    return run


class _Response:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_URL", "https://radar.example.dev/")
    monkeypatch.setenv("RADAR_ONLINE_API_KEY", _KEY)


@pytest.fixture
def sent(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response(json.dumps({"report_path": "/u/ada/summit-stats"}).encode())

    monkeypatch.setattr(publishing, "urlopen", fake_urlopen)
    return requests


def _fail_with(monkeypatch, error):
    def fake_urlopen(request, timeout):
        raise error

    monkeypatch.setattr(publishing, "urlopen", fake_urlopen)


def test_publishing_posts_the_payload_and_returns_the_public_url(db_session, configured, sent):
    run = make_scoring_run(db_session)

    url = publish_scoring_run(db_session, run)

    assert url == "https://radar.example.dev/u/ada/summit-stats"
    (request,) = sent
    assert request.full_url == "https://radar.example.dev/api/reports"
    assert request.get_method() == "POST"
    assert request.get_header("X-api-key") == _KEY
    assert request.get_header("Content-type") == "application/json"
    expected = build_publication_payload(db_session, run).model_dump(mode="json")
    assert json.loads(request.data) == expected


def test_a_dirty_audit_is_never_sent(db_session, configured, sent):
    run = make_scoring_run(db_session, is_dirty=True)

    with pytest.raises(DirtyAuditError):
        publish_scoring_run(db_session, run)

    assert sent == []


@pytest.mark.parametrize(
    ("url", "key"),
    [
        (None, _KEY),
        ("https://radar.example.dev", None),
        ("", _KEY),
        ("file:///etc/passwd", _KEY),
    ],
)
def test_missing_or_unsafe_configuration_sends_nothing(db_session, monkeypatch, sent, url, key):
    for name, value in (("RADAR_ONLINE_URL", url), ("RADAR_ONLINE_API_KEY", key)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    run = make_scoring_run(db_session)

    with pytest.raises(PublishingNotConfiguredError):
        publish_scoring_run(db_session, run)

    assert sent == []


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {"detail": "invalid or missing API key"}, "invalid or missing API key"),
        (422, {"detail": [{"msg": "bad value"}]}, "bad value"),
    ],
)
def test_a_server_refusal_reports_its_status_and_detail(
    db_session, configured, monkeypatch, status, body, expected
):
    error = HTTPError(
        "https://radar.example.dev/api/reports",
        status,
        "refused",
        {},
        io.BytesIO(json.dumps(body).encode()),
    )
    _fail_with(monkeypatch, error)
    run = make_scoring_run(db_session)

    with pytest.raises(PublishFailedError) as exc_info:
        publish_scoring_run(db_session, run)

    assert str(status) in str(exc_info.value)
    assert expected in str(exc_info.value)
    assert _KEY not in str(exc_info.value)


def test_a_network_error_is_reported(db_session, configured, monkeypatch):
    _fail_with(monkeypatch, URLError("connection refused"))
    run = make_scoring_run(db_session)

    with pytest.raises(PublishFailedError, match="connection refused"):
        publish_scoring_run(db_session, run)
