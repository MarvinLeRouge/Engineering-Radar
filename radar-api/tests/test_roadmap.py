from radar_core.enums import Confidence, EvidenceType, FindingSeverity, RoadmapStatus, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding
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


def _make_finding_chain(db_session, repository, commit_sha="a" * 40):
    audit = Audit(repository_id=repository.id, commit_sha=commit_sha, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}-{commit_sha[:8]}")
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


def _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO, title="Fix it", priority=1):
    task = ImprovementTask(
        title=title,
        description="...",
        criterion_id=finding.criterion_id,
        file=None,
        group_key=f"fix-it-{finding.id}",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=status, priority=priority)
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


def test_list_roadmap_items_deduplicates_item_linked_to_multiple_findings(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap-dedup")
    finding_a = _make_finding_chain(db_session, repo, commit_sha="a" * 40)
    finding_b = _make_finding_chain(db_session, repo, commit_sha="b" * 40)

    task = ImprovementTask(
        title="Fix both",
        description="...",
        criterion_id=finding_a.criterion_id,
        file=None,
        group_key="fix-both",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding_a.id, improvement_task_id=task.id))
    db_session.add(FindingImprovementTaskLink(finding_id=finding_b.id, improvement_task_id=task.id))
    db_session.commit()

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=RoadmapStatus.TODO, priority=1)
    db_session.add(roadmap_item)
    db_session.commit()

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1


def _make_evidence(db_session, finding):
    evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.HUMAN_CONFIRMATION,
        content="fixed in PR #123",
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


def test_update_roadmap_item_status_requires_api_key(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap-noauth")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status", json={"status": "IN_PROGRESS"}
    )

    assert response.status_code == 401


def test_update_roadmap_item_status_returns_404_when_missing(client, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    response = client.patch(
        "/roadmap-items/999/status",
        json={"status": "IN_PROGRESS"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 404


def test_update_roadmap_item_status_rejects_no_op_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-noop")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "TODO"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_roadmap_item_status_rejects_done_without_evidence(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-done-no-evidence")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 422


def test_update_roadmap_item_status_rejects_nonexistent_evidence(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-bad-evidence")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE", "done_evidence_id": 999},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_roadmap_item_status_rejects_evidence_from_unrelated_finding(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-unrelated-evidence")
    finding_a = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding_a, status=RoadmapStatus.IN_PROGRESS)

    other_repo = _make_repository(db_session, "repo-roadmap-unrelated-evidence-other")
    finding_b = _make_finding_chain(db_session, other_repo)
    evidence = _make_evidence(db_session, finding_b)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE", "done_evidence_id": evidence.id},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_roadmap_item_status_succeeds_for_non_done_transition(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-in-progress")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_update_roadmap_item_status_succeeds_for_done_with_evidence(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-done")
    finding = _make_finding_chain(db_session, repo)
    evidence = _make_evidence(db_session, finding)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE", "done_evidence_id": evidence.id},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DONE"
    assert body["done_at"] is not None


def test_update_roadmap_item_status_clears_done_fields_on_reopen(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-reopen")
    finding = _make_finding_chain(db_session, repo)
    evidence = _make_evidence(db_session, finding)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    done_response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE", "done_evidence_id": evidence.id},
        headers={"X-API-Key": "secret"},
    )
    assert done_response.status_code == 200

    reopen_response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"X-API-Key": "secret"},
    )

    assert reopen_response.status_code == 200
    body = reopen_response.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["done_at"] is None

    db_session.refresh(roadmap_item)
    assert roadmap_item.done_evidence_id is None


def test_evidence_candidates_returns_404_when_roadmap_item_missing(client):
    response = client.get("/roadmap-items/999/evidence-candidates")

    assert response.status_code == 404


def test_evidence_candidates_returns_empty_list_when_none_linked(client, db_session):
    repo = _make_repository(db_session, "repo-evidence-empty")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
    assert response.json() == []


def test_evidence_candidates_returns_evidence_linked_via_finding(client, db_session):
    repo = _make_repository(db_session, "repo-evidence")
    finding = _make_finding_chain(db_session, repo)
    evidence = _make_evidence(db_session, finding)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == evidence.id
    assert body[0]["finding_id"] == finding.id
    assert body[0]["evidence_type"] == "HUMAN_CONFIRMATION"
    assert body[0]["content"] == "fixed in PR #123"


def test_evidence_candidates_excludes_evidence_from_unrelated_finding(client, db_session):
    repo = _make_repository(db_session, "repo-evidence-unrelated")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    other_repo = _make_repository(db_session, "repo-evidence-unrelated-other")
    other_finding = _make_finding_chain(db_session, other_repo)
    _make_evidence(db_session, other_finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
    assert response.json() == []


def test_evidence_candidates_no_api_key_required(client, db_session):
    repo = _make_repository(db_session, "repo-evidence-no-auth")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200


def test_list_roadmap_items_includes_task_title_and_description(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap-title")
    finding = _make_finding_chain(db_session, repo)
    _make_roadmap_item(db_session, finding)

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["title"] == "Fix it"
    assert body[0]["description"] == "..."
    assert body[0]["category_name"] == "Security"
    assert body[0]["criterion_name"] == "SAST findings"


def test_list_roadmap_items_sorted_by_category_order_then_criterion(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap-sorted")

    audit = Audit(repository_id=repo.id, commit_sha="c" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-sorted-{repo.id}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    category_a = Category(
        methodology_version_id=methodology_version.id, name="Z Category", weight=1.0, order=2
    )
    category_b = Category(
        methodology_version_id=methodology_version.id, name="A Category", weight=1.0, order=1
    )
    db_session.add(category_a)
    db_session.add(category_b)
    db_session.commit()
    db_session.refresh(category_a)
    db_session.refresh(category_b)

    criterion_a = Criterion(
        category_id=category_a.id,
        name="Criterion in Z",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    criterion_b = Criterion(
        category_id=category_b.id,
        name="Criterion in A",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion_a)
    db_session.add(criterion_b)
    db_session.commit()
    db_session.refresh(criterion_a)
    db_session.refresh(criterion_b)

    finding_a = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion_a.id,
        severity=FindingSeverity.HIGH,
        description="in z category",
        confidence=Confidence.HIGH,
    )
    finding_b = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion_b.id,
        severity=FindingSeverity.HIGH,
        description="in a category",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding_a)
    db_session.add(finding_b)
    db_session.commit()
    db_session.refresh(finding_a)
    db_session.refresh(finding_b)

    _make_roadmap_item(db_session, finding_a)
    _make_roadmap_item(db_session, finding_b)

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["category_name"] == "A Category"
    assert body[1]["category_name"] == "Z Category"


def test_list_roadmap_items_sorted_by_priority_desc_then_title_asc_within_criterion(
    client, db_session
):
    repo = _make_repository(db_session, "repo-roadmap-priority-sort")
    finding_low = _make_finding_chain(db_session, repo)

    finding_high = Finding(
        scoring_run_id=finding_low.scoring_run_id,
        criterion_id=finding_low.criterion_id,
        severity=FindingSeverity.HIGH,
        description="another issue",
        confidence=Confidence.HIGH,
    )
    finding_tie = Finding(
        scoring_run_id=finding_low.scoring_run_id,
        criterion_id=finding_low.criterion_id,
        severity=FindingSeverity.HIGH,
        description="yet another issue",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding_high)
    db_session.add(finding_tie)
    db_session.commit()
    db_session.refresh(finding_high)
    db_session.refresh(finding_tie)

    _make_roadmap_item(db_session, finding_low, title="B item", priority=1)
    _make_roadmap_item(db_session, finding_high, title="Z item", priority=5)
    _make_roadmap_item(db_session, finding_tie, title="A item", priority=5)

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body] == ["A item", "Z item", "B item"]
