from radar_core.enums import Confidence, ScoreLevel, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun


def _add(db_session, row):
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _scored_repository(db_session, is_dirty=False):
    repository = _add(db_session, Repository(name="Summit-Stats", path="/tmp/summit-stats"))
    audit = _add(
        db_session, Audit(repository_id=repository.id, commit_sha="d" * 40, is_dirty=is_dirty)
    )
    version = _add(db_session, MethodologyVersion(version_label="Quality Framework v1.0"))
    run = _add(
        db_session,
        ScoringRun(audit_id=audit.id, methodology_version_id=version.id, global_score=6.2),
    )
    category = _add(
        db_session,
        Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4),
    )
    _add(
        db_session,
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
        db_session,
        Score(
            scoring_run_id=run.id,
            category_id=category.id,
            level=ScoreLevel.CATEGORY,
            value=6.2,
            confidence=Confidence.MEDIUM,
        ),
    )
    return repository


def test_preview_returns_the_payload_of_the_latest_run(client, db_session):
    repository = _scored_repository(db_session)

    response = client.get(f"/repositories/{repository.id}/publish-preview")

    assert response.status_code == 200
    body = response.json()
    assert body["is_dirty"] is False
    assert body["payload"]["repository"] == {"slug": "summit-stats", "display_name": "Summit-Stats"}
    assert body["payload"]["commit_sha"] == "d" * 40
    assert body["payload"]["global_score"] == 6.2
    assert body["payload"]["categories"] == [
        {
            "name": "Security",
            "order": 4,
            "weight": 1.5,
            "status": "scored",
            "implemented": True,
            "value": 6.2,
            "confidence": "MEDIUM",
        }
    ]


def test_preview_flags_a_dirty_audit(client, db_session):
    repository = _scored_repository(db_session, is_dirty=True)

    response = client.get(f"/repositories/{repository.id}/publish-preview")

    assert response.json()["is_dirty"] is True


def test_preview_of_an_unknown_repository_is_not_found(client):
    assert client.get("/repositories/999/publish-preview").status_code == 404


def test_preview_of_an_unscored_repository_is_not_found(client, db_session):
    repository = _add(db_session, Repository(name="fresh", path="/tmp/fresh"))

    assert client.get(f"/repositories/{repository.id}/publish-preview").status_code == 404
