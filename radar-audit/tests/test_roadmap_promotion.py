from radar_audit.normalizers.shared import (
    add_finding_with_recommendation,
    get_criterion,
    get_or_create_scoring_run,
)
from radar_audit.roadmap_promotion import promote_improvement_tasks
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, RoadmapStatus
from radar_core.finding_fingerprint import compute_fingerprint
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from sqlmodel import select


def _setup(db_session, commit_sha="a" * 40):
    repo = Repository(name="fixture", path="/tmp/fixture-roadmap-promotion")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha=commit_sha, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    return repo, audit, scoring_run, methodology_version


def _add_finding(session, scoring_run, criterion, description, file, severity=FindingSeverity.LOW):
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=severity,
        description=description,
        file=file,
        fingerprint=compute_fingerprint(criterion.id, severity, file, description),
        confidence=Confidence.HIGH,
        status=FindingStatus.OPEN,
        human_verdict=HumanVerdict.UNREVIEWED,
    )
    add_finding_with_recommendation(session, finding, "Fix this.")
    session.commit()
    return finding


def test_two_findings_in_the_same_criterion_and_file_share_one_task(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Linter clean pass rate")
    _add_finding(db_session, scoring_run, criterion, "E501: line too long", "src/a.py")
    _add_finding(db_session, scoring_run, criterion, "F401: unused import", "src/a.py")

    promote_improvement_tasks(db_session, scoring_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 1
    assert tasks[0].title == "Linter clean pass rate: src/a.py"
    links = db_session.exec(
        select(FindingImprovementTaskLink).where(
            FindingImprovementTaskLink.improvement_task_id == tasks[0].id
        )
    ).all()
    assert len(links) == 2


def test_description_includes_recommendation_and_each_finding(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Linter clean pass rate")
    _add_finding(db_session, scoring_run, criterion, "E501: line too long", "src/a.py")
    _add_finding(db_session, scoring_run, criterion, "F401: unused import", "src/a.py")

    promote_improvement_tasks(db_session, scoring_run)

    task = db_session.exec(select(ImprovementTask)).one()
    assert "Fix this." in task.description
    assert "E501: line too long" in task.description
    assert "F401: unused import" in task.description


def test_different_files_get_different_tasks(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Linter clean pass rate")
    _add_finding(db_session, scoring_run, criterion, "E501: line too long", "src/a.py")
    _add_finding(db_session, scoring_run, criterion, "E501: line too long", "src/b.py")

    promote_improvement_tasks(db_session, scoring_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 2


def test_findings_with_no_file_are_atomic_one_task_each(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Security", "Dependency vulnerabilities (CVE)")
    _add_finding(db_session, scoring_run, criterion, "CVE-1: vulnerable dependency foo", None)
    _add_finding(db_session, scoring_run, criterion, "CVE-2: vulnerable dependency bar", None)

    promote_improvement_tasks(db_session, scoring_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 2


def test_code_duplication_findings_bypass_file_grouping_even_with_the_same_file(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Code duplication")
    _add_finding(
        db_session, scoring_run, criterion, "Duplicated block between a.js and b.js", "a.js"
    )
    _add_finding(
        db_session, scoring_run, criterion, "Duplicated block between a.js and c.js", "a.js"
    )

    promote_improvement_tasks(db_session, scoring_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 2


def test_dependency_circularity_findings_are_atomic(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(
        db_session, mv.id, "Architecture & design", "Dependency direction / circularity"
    )
    _add_finding(db_session, scoring_run, criterion, "Circular dependency involving: a, b", "a.py")
    _add_finding(db_session, scoring_run, criterion, "Circular dependency involving: c, d", "a.py")

    promote_improvement_tasks(db_session, scoring_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 2


def test_priority_reflects_the_worst_severity_in_the_group(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Security", "SAST findings")
    _add_finding(
        db_session, scoring_run, criterion, "low issue", "a.py", severity=FindingSeverity.LOW
    )
    _add_finding(
        db_session,
        scoring_run,
        criterion,
        "critical issue",
        "a.py",
        severity=FindingSeverity.CRITICAL,
    )

    promote_improvement_tasks(db_session, scoring_run)

    task = db_session.exec(select(ImprovementTask)).one()
    roadmap_item = db_session.exec(
        select(RoadmapItem).where(RoadmapItem.improvement_task_id == task.id)
    ).one()
    # worst severity = CRITICAL -> rank 4, files_impacted = files_to_fix = 1 -> ROI = 4.0
    assert roadmap_item.priority == 4.0


def test_re_promoting_the_same_group_upserts_instead_of_duplicating(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Linter clean pass rate")
    _add_finding(db_session, scoring_run, criterion, "E501: line too long", "src/a.py")

    promote_improvement_tasks(db_session, scoring_run)
    promote_improvement_tasks(db_session, scoring_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 1


def test_human_set_status_and_effort_survive_a_re_promotion_on_a_new_scoring_run(db_session):
    repo, _, first_run, mv = _setup(db_session, commit_sha="a" * 40)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Linter clean pass rate")
    _add_finding(db_session, first_run, criterion, "E501: line too long", "src/a.py")
    promote_improvement_tasks(db_session, first_run)

    task = db_session.exec(select(ImprovementTask)).one()
    roadmap_item = db_session.exec(
        select(RoadmapItem).where(RoadmapItem.improvement_task_id == task.id)
    ).one()
    roadmap_item.status = RoadmapStatus.IN_PROGRESS
    roadmap_item.estimated_effort = "2h"
    db_session.add(roadmap_item)
    db_session.commit()

    second_audit = Audit(repository_id=repo.id, commit_sha="b" * 40, is_dirty=False)
    db_session.add(second_audit)
    db_session.commit()
    db_session.refresh(second_audit)
    second_run = get_or_create_scoring_run(db_session, second_audit, mv)
    _add_finding(db_session, second_run, criterion, "E501: line too long", "src/a.py")

    promote_improvement_tasks(db_session, second_run)

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 1
    refreshed_item = db_session.exec(
        select(RoadmapItem).where(RoadmapItem.improvement_task_id == tasks[0].id)
    ).one()
    assert refreshed_item.status == RoadmapStatus.IN_PROGRESS
    assert refreshed_item.estimated_effort == "2h"


def test_duplication_priority_counts_distinct_files_across_a_collided_group(db_session):
    _, _, scoring_run, mv = _setup(db_session)
    criterion = get_criterion(db_session, mv.id, "Code quality", "Code duplication")
    first = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.LOW,
        description="Duplicated block between a.js:1-20 and b.js:1-20",
        file="a.js",
        fingerprint="collided-fingerprint",
        confidence=Confidence.HIGH,
        status=FindingStatus.OPEN,
        human_verdict=HumanVerdict.UNREVIEWED,
    )
    second = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.LOW,
        description="Duplicated block between a.js:40-59 and c.js:1-20",
        file="a.js",
        fingerprint="collided-fingerprint",
        confidence=Confidence.HIGH,
        status=FindingStatus.OPEN,
        human_verdict=HumanVerdict.UNREVIEWED,
    )
    add_finding_with_recommendation(db_session, first, "Fix this.")
    add_finding_with_recommendation(db_session, second, "Fix this.")
    db_session.commit()

    promote_improvement_tasks(db_session, scoring_run)

    task = db_session.exec(select(ImprovementTask)).one()
    links = db_session.exec(
        select(FindingImprovementTaskLink).where(
            FindingImprovementTaskLink.improvement_task_id == task.id
        )
    ).all()
    assert len(links) == 2
    roadmap_item = db_session.exec(
        select(RoadmapItem).where(RoadmapItem.improvement_task_id == task.id)
    ).one()
    # 3 distinct files (a.js, b.js, c.js) x LOW severity (rank 1.0) / 1 = 3.0
    assert roadmap_item.priority == 3.0
