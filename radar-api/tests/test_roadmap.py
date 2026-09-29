from radar_core.enums import Confidence, FindingSeverity, RoadmapStatus, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_finding_chain(db_session, repository):
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

    category = Category(
        methodology_version_id=methodology_version.id, name="Security", weight=1.0, order=1
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

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.HIGH,
        description="issue",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO):
    task = ImprovementTask(title="Fix it", description="...")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=status, priority=1)
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)
    return roadmap_item


def test_list_roadmap_items_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/roadmap")

    assert response.status_code == 404


def test_list_roadmap_items_returns_empty_list_when_none(client, db_session):
    repo = _make_repository(db_session, "repo-no-roadmap")

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    assert response.json() == []


def test_list_roadmap_items_returns_items_linked_via_findings(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap")
    finding = _make_finding_chain(db_session, repo)
    _make_roadmap_item(db_session, finding)

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "TODO"
