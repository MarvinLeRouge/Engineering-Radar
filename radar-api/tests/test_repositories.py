from radar_core.enums import Confidence, FindingSeverity, ScoreLevel, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_scoring_run(db_session, repository, global_score):
    audit = Audit(repository_id=repository.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}-{global_score}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(
        audit_id=audit.id,
        methodology_version_id=methodology_version.id,
        global_score=global_score,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)
    return scoring_run


def test_list_repositories_returns_not_yet_audited_when_no_scoring_run(client, db_session):
    _make_repository(db_session, "repo-a")

    response = client.get("/repositories")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["audit_status"] == "not_yet_audited"
    assert body[0]["global_score"] is None


def test_list_repositories_returns_global_score_when_scored(client, db_session):
    repo = _make_repository(db_session, "repo-b")
    _make_scoring_run(db_session, repo, global_score=7.5)

    response = client.get("/repositories")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["audit_status"] == "scored"
    assert body[0]["global_score"] == 7.5


def test_get_repository_returns_404_when_missing(client):
    response = client.get("/repositories/999")

    assert response.status_code == 404


def test_get_repository_returns_detail(client, db_session):
    repo = _make_repository(db_session, "repo-c")

    response = client.get(f"/repositories/{repo.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "repo-c"


def _seed_category_and_criterion(db_session, methodology_version_id, name="Dependency vulns"):
    category = Category(
        methodology_version_id=methodology_version_id, name="Security", weight=1.0, order=1
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name=name,
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)
    return category, criterion


def test_get_repository_report_returns_404_when_no_score(client, db_session):
    repo = _make_repository(db_session, "repo-no-score")

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 404


def test_get_repository_report_includes_findings_and_recommendations(client, db_session):
    repo = _make_repository(db_session, "repo-with-findings")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    category, criterion = _seed_category_and_criterion(
        db_session, scoring_run.methodology_version_id
    )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=4.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(score)
    db_session.commit()

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.HIGH,
        description="a vulnerable dependency",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    db_session.add(Recommendation(finding_id=finding.id, text="upgrade the dependency"))
    db_session.commit()

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    body = response.json()
    criterion_report = body["categories"][0]["criteria"][0]
    assert criterion_report["status"] == "scored"
    assert criterion_report["value"] == 4.0
    assert criterion_report["findings"][0]["recommendation"] == "upgrade the dependency"


def test_get_repository_report_marks_unscored_criterion_as_not_yet_audited(client, db_session):
    repo = _make_repository(db_session, "repo-partial")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    _seed_category_and_criterion(db_session, scoring_run.methodology_version_id)

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    criterion_report = response.json()["categories"][0]["criteria"][0]
    assert criterion_report["status"] == "not_yet_audited"
    assert criterion_report["value"] is None


def test_badge_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/badge")

    assert response.status_code == 404


def test_badge_shows_not_yet_audited_when_no_scoring_run(client, db_session):
    repo = _make_repository(db_session, "repo-badge-unscored")

    response = client.get(f"/repositories/{repo.id}/badge")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "not yet audited"
    assert body["color"] == "lightgrey"
    assert body["schemaVersion"] == 1


def test_badge_shows_not_yet_audited_when_global_score_is_none(client, db_session):
    repo = _make_repository(db_session, "repo-badge-null-score")
    _make_scoring_run(db_session, repo, global_score=None)

    response = client.get(f"/repositories/{repo.id}/badge")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "not yet audited"
    assert body["color"] == "lightgrey"


def test_badge_color_reflects_global_score(client, db_session):
    repo = _make_repository(db_session, "repo-badge-high-score")
    _make_scoring_run(db_session, repo, global_score=8.5)

    response = client.get(f"/repositories/{repo.id}/badge")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "8.5/10"
    assert body["color"] == "brightgreen"
