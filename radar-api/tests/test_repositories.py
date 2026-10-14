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


def _make_scoring_run(db_session, repository, global_score, commit_sha="a" * 40):
    audit = Audit(repository_id=repository.id, commit_sha=commit_sha, is_dirty=False)
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


def test_get_repository_report_orders_findings_by_severity_then_magnitude(client, db_session):
    repo = _make_repository(db_session, "repo-with-ordered-findings")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    category, criterion = _seed_category_and_criterion(
        db_session, scoring_run.methodology_version_id
    )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=2.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(score)
    low_magnitude = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.MEDIUM,
        description="small has cyclomatic complexity 11",
        magnitude=11.0,
        confidence=Confidence.HIGH,
    )
    high_magnitude = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.MEDIUM,
        description="worst has cyclomatic complexity 42",
        magnitude=42.0,
        confidence=Confidence.HIGH,
    )
    # Inserted in an order that would be wrong if findings were left unsorted.
    db_session.add(low_magnitude)
    db_session.add(high_magnitude)
    db_session.commit()

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    findings = response.json()["categories"][0]["criteria"][0]["findings"]
    descriptions = [f["description"] for f in findings]
    assert descriptions == [
        "worst has cyclomatic complexity 42",
        "small has cyclomatic complexity 11",
    ]


def test_get_repository_report_marks_unscored_criterion_as_not_yet_audited(client, db_session):
    repo = _make_repository(db_session, "repo-partial")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    _seed_category_and_criterion(db_session, scoring_run.methodology_version_id)

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    criterion_report = response.json()["categories"][0]["criteria"][0]
    assert criterion_report["status"] == "not_yet_audited"
    assert criterion_report["value"] is None


def test_get_repository_report_marks_not_applicable_criterion_with_null_value(client, db_session):
    repo = _make_repository(db_session, "repo-na-criterion")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    _category, criterion = _seed_category_and_criterion(
        db_session, scoring_run.methodology_version_id
    )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=0.0,
        confidence=Confidence.HIGH,
        na_reason="no dependencies to scan",
    )
    db_session.add(score)
    db_session.commit()

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    criterion_report = response.json()["categories"][0]["criteria"][0]
    assert criterion_report["status"] == "not_applicable"
    assert criterion_report["value"] is None


def test_get_repository_report_with_scoring_run_id_returns_that_specific_run(client, db_session):
    repo = _make_repository(db_session, "repo-history")
    older_run = _make_scoring_run(db_session, repo, global_score=3.0, commit_sha="a" * 40)
    _seed_category_and_criterion(db_session, older_run.methodology_version_id)
    newer_run = _make_scoring_run(db_session, repo, global_score=8.0, commit_sha="b" * 40)
    _seed_category_and_criterion(db_session, newer_run.methodology_version_id)

    response = client.get(f"/repositories/{repo.id}/report?scoring_run_id={older_run.id}")

    assert response.status_code == 200
    assert response.json()["scored_at"] is not None
    # Without the param, the latest run (8.0) would be returned instead.
    default_response = client.get(f"/repositories/{repo.id}/report")
    assert default_response.json() != response.json()


def test_get_repository_report_returns_404_for_unknown_scoring_run_id(client, db_session):
    repo = _make_repository(db_session, "repo-bad-history")
    _make_scoring_run(db_session, repo, global_score=5.0)

    response = client.get(f"/repositories/{repo.id}/report?scoring_run_id=999999")

    assert response.status_code == 404


def test_get_repository_report_returns_404_when_scoring_run_belongs_to_another_repository(
    client, db_session
):
    repo_a = _make_repository(db_session, "repo-mine")
    repo_b = _make_repository(db_session, "repo-other")
    _make_scoring_run(db_session, repo_a, global_score=5.0)
    other_run = _make_scoring_run(db_session, repo_b, global_score=9.0)

    response = client.get(f"/repositories/{repo_a.id}/report?scoring_run_id={other_run.id}")

    assert response.status_code == 404


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
