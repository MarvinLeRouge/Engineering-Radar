from radar_core.enums import Confidence, FindingSeverity, FindingStatus, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_scoring_run(db_session, repository):
    audit = Audit(repository_id=repository.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)
    return scoring_run


def _make_criterion(db_session, methodology_version_id):
    category = Category(
        methodology_version_id=methodology_version_id, name="Security", weight=1.0, order=1
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="SAST findings",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)
    return criterion


def _make_finding(
    db_session, scoring_run, criterion, severity=FindingSeverity.HIGH, status=FindingStatus.OPEN
):
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=severity,
        description="issue",
        confidence=Confidence.HIGH,
        status=status,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_list_findings_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/findings")

    assert response.status_code == 404


def test_list_findings_returns_empty_list_when_none(client, db_session):
    repo = _make_repository(db_session, "repo-no-findings")

    response = client.get(f"/repositories/{repo.id}/findings")

    assert response.status_code == 200
    assert response.json() == []


def test_list_findings_returns_findings_for_latest_scoring_run(client, db_session):
    repo = _make_repository(db_session, "repo-findings")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    _make_finding(db_session, scoring_run, criterion)

    response = client.get(f"/repositories/{repo.id}/findings")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["severity"] == "HIGH"


def test_list_findings_filters_by_status(client, db_session):
    repo = _make_repository(db_session, "repo-findings-filter")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    _make_finding(db_session, scoring_run, criterion, status=FindingStatus.OPEN)
    _make_finding(db_session, scoring_run, criterion, status=FindingStatus.RESOLVED)

    response = client.get(f"/repositories/{repo.id}/findings", params={"status": "RESOLVED"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "RESOLVED"


def test_list_findings_filters_by_severity(client, db_session):
    repo = _make_repository(db_session, "repo-findings-severity")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    _make_finding(db_session, scoring_run, criterion, severity=FindingSeverity.CRITICAL)
    _make_finding(db_session, scoring_run, criterion, severity=FindingSeverity.LOW)

    response = client.get(f"/repositories/{repo.id}/findings", params={"severity": "CRITICAL"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["severity"] == "CRITICAL"


def test_update_finding_verdict_requires_api_key(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-noauth")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict", json={"human_verdict": "TRUE_POSITIVE"}
    )

    assert response.status_code == 401


def test_update_finding_verdict_returns_404_when_missing(client, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    response = client.patch(
        "/findings/999/verdict",
        json={"human_verdict": "TRUE_POSITIVE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 404


def test_update_finding_verdict_rejects_unknown_enum_value(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-bad-enum")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict",
        json={"human_verdict": "NOT_A_VALUE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 422


def test_update_finding_verdict_rejects_no_op_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-noop")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict",
        json={"human_verdict": "UNREVIEWED"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_finding_verdict_succeeds(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-ok")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict",
        json={"human_verdict": "TRUE_POSITIVE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["human_verdict"] == "TRUE_POSITIVE"


def test_update_finding_status_requires_api_key(client, db_session):
    repo = _make_repository(db_session, "repo-status-noauth")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(f"/findings/{finding.id}/status", json={"status": "RESOLVED"})

    assert response.status_code == 401


def test_update_finding_status_rejects_no_op_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-status-noop")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion, status=FindingStatus.OPEN)

    response = client.patch(
        f"/findings/{finding.id}/status",
        json={"status": "OPEN"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_finding_status_succeeds(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-status-ok")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion, status=FindingStatus.OPEN)

    response = client.patch(
        f"/findings/{finding.id}/status",
        json={"status": "WONT_FIX"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "WONT_FIX"
