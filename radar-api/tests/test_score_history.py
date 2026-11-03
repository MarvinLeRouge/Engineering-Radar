from datetime import datetime

from radar_core.enums import (
    Confidence,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    ScoreLevel,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_scoring_run(db_session, repository, commit_sha, scored_at, global_score):
    audit = Audit(repository_id=repository.id, commit_sha=commit_sha, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{audit.id}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(
        audit_id=audit.id,
        methodology_version_id=methodology_version.id,
        global_score=global_score,
        scored_at=datetime.fromisoformat(scored_at),
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)
    return audit, scoring_run


def _make_category(db_session, methodology_version_id, name, order, weight=1.0):
    category = Category(
        methodology_version_id=methodology_version_id, name=name, weight=weight, order=order
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def _make_category_score(db_session, scoring_run_id, category_id, value):
    score = Score(
        scoring_run_id=scoring_run_id,
        category_id=category_id,
        level=ScoreLevel.CATEGORY,
        value=value,
        confidence=Confidence.HIGH,
    )
    db_session.add(score)
    db_session.commit()


def test_score_history_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/score-history")

    assert response.status_code == 404


def test_score_history_returns_empty_list_when_not_yet_audited(client, db_session):
    repo = _make_repository(db_session, "repo-no-history")

    response = client.get(f"/repositories/{repo.id}/score-history")

    assert response.status_code == 200
    assert response.json() == []


def test_score_history_returns_points_ordered_chronologically(client, db_session):
    repo = _make_repository(db_session, "repo-with-history")
    _audit1, run1 = _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00+00:00", 5.0)
    _audit2, run2 = _make_scoring_run(db_session, repo, "b" * 40, "2026-03-01T00:00:00+00:00", 7.0)
    # Inserted out of chronological order, response must still sort by scored_at.
    _audit0, run0 = _make_scoring_run(db_session, repo, "c" * 40, "2025-06-01T00:00:00+00:00", 3.0)

    response = client.get(f"/repositories/{repo.id}/score-history")

    assert response.status_code == 200
    body = response.json()
    assert [p["global_score"] for p in body] == [3.0, 5.0, 7.0]
    assert [p["scoring_run_id"] for p in body] == [run0.id, run1.id, run2.id]


def test_score_history_includes_commit_sha_and_null_global_score(client, db_session):
    repo = _make_repository(db_session, "repo-null-score")
    audit, run = _make_scoring_run(db_session, repo, "d" * 40, "2026-01-01T00:00:00+00:00", None)

    response = client.get(f"/repositories/{repo.id}/score-history")

    assert response.status_code == 200
    point = response.json()[0]
    assert point["audit_id"] == audit.id
    assert point["commit_sha"] == "d" * 40
    assert point["global_score"] is None


def test_score_history_only_includes_this_repositorys_runs(client, db_session):
    repo_a = _make_repository(db_session, "repo-a")
    repo_b = _make_repository(db_session, "repo-b")
    _make_scoring_run(db_session, repo_a, "a" * 40, "2026-01-01T00:00:00+00:00", 5.0)
    _make_scoring_run(db_session, repo_b, "b" * 40, "2026-01-01T00:00:00+00:00", 9.0)

    response = client.get(f"/repositories/{repo_a.id}/score-history")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["global_score"] == 5.0


def test_score_history_includes_category_scores_ordered_by_category_order(client, db_session):
    repo = _make_repository(db_session, "repo-with-categories")
    _audit, run = _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00+00:00", 5.0)
    security = _make_category(db_session, run.methodology_version_id, "Security", order=2)
    architecture = _make_category(db_session, run.methodology_version_id, "Architecture", order=1)
    _make_category_score(db_session, run.id, architecture.id, 8.0)
    _make_category_score(db_session, run.id, security.id, 4.0)

    response = client.get(f"/repositories/{repo.id}/score-history")

    assert response.status_code == 200
    categories = response.json()[0]["categories"]
    assert categories == [
        {"id": architecture.id, "name": "Architecture", "value": 8.0},
        {"id": security.id, "name": "Security", "value": 4.0},
    ]


def test_score_history_reports_null_value_for_category_not_yet_scored(client, db_session):
    repo = _make_repository(db_session, "repo-partial-category")
    _audit, run = _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00+00:00", 5.0)
    _make_category(db_session, run.methodology_version_id, "Performance", order=1)

    response = client.get(f"/repositories/{repo.id}/score-history")

    assert response.status_code == 200
    categories = response.json()[0]["categories"]
    assert categories == [{"id": categories[0]["id"], "name": "Performance", "value": None}]


def test_score_history_does_not_leak_categories_across_methodology_versions(client, db_session):
    repo = _make_repository(db_session, "repo-methodology-upgrade")
    _audit1, run1 = _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00+00:00", 5.0)
    _audit2, run2 = _make_scoring_run(db_session, repo, "b" * 40, "2026-02-01T00:00:00+00:00", 6.0)
    assert run1.methodology_version_id != run2.methodology_version_id

    old_category = _make_category(db_session, run1.methodology_version_id, "Old category", order=1)
    new_category = _make_category(db_session, run2.methodology_version_id, "New category", order=1)
    _make_category_score(db_session, run1.id, old_category.id, 5.0)
    _make_category_score(db_session, run2.id, new_category.id, 6.0)

    response = client.get(f"/repositories/{repo.id}/score-history")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["categories"] == [{"id": old_category.id, "name": "Old category", "value": 5.0}]
    assert body[1]["categories"] == [{"id": new_category.id, "name": "New category", "value": 6.0}]


def _add_findings(db_session, scoring_run, severity, count, **overrides):
    category = _make_category(db_session, scoring_run.methodology_version_id, f"c-{severity}", 99)
    criterion = Criterion(
        category_id=category.id,
        name="crit",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)
    for _ in range(count):
        db_session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                severity=severity,
                description="issue",
                confidence=Confidence.HIGH,
                **overrides,
            )
        )
    db_session.commit()


def test_score_history_reports_weighted_risk_per_severity(client, db_session):
    repo = _make_repository(db_session)
    _, run = _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00", 5.0)
    _add_findings(db_session, run, FindingSeverity.CRITICAL, 2)
    _add_findings(db_session, run, FindingSeverity.LOW, 3)

    point = client.get(f"/repositories/{repo.id}/score-history").json()[0]

    risk = {entry["severity"]: entry for entry in point["risk"]}
    assert list(risk) == ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert risk["CRITICAL"] == {
        "severity": "CRITICAL",
        "weight": 64,
        "count": 2,
        "excluded": 0,
        "wont_fix": 0,
        "weighted": 128,
    }
    assert risk["HIGH"]["count"] == 0
    assert risk["LOW"]["weighted"] == 3
    assert point["risk_index"] == 131


def test_score_history_risk_excludes_closed_and_false_positive_findings(client, db_session):
    repo = _make_repository(db_session)
    _, run = _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00", 5.0)
    _add_findings(db_session, run, FindingSeverity.HIGH, 1)
    _add_findings(db_session, run, FindingSeverity.HIGH, 1, status=FindingStatus.RESOLVED)
    _add_findings(db_session, run, FindingSeverity.HIGH, 1, status=FindingStatus.WONT_FIX)
    _add_findings(
        db_session, run, FindingSeverity.HIGH, 1, human_verdict=HumanVerdict.FALSE_POSITIVE
    )

    point = client.get(f"/repositories/{repo.id}/score-history").json()[0]

    high = next(entry for entry in point["risk"] if entry["severity"] == "HIGH")
    assert high == {
        "severity": "HIGH",
        "weight": 16,
        "count": 1,
        "excluded": 3,
        "wont_fix": 1,
        "weighted": 16,
    }
    assert point["risk_index"] == 16


def test_score_history_risk_is_zero_without_findings(client, db_session):
    repo = _make_repository(db_session)
    _make_scoring_run(db_session, repo, "a" * 40, "2026-01-01T00:00:00", 5.0)

    point = client.get(f"/repositories/{repo.id}/score-history").json()[0]

    assert point["risk_index"] == 0
    assert all(entry["count"] == 0 for entry in point["risk"])
