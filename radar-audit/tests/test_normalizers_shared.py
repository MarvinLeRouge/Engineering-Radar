import pytest
from radar_audit.normalizers.shared import (
    CriterionNotFoundError,
    add_finding_with_recommendation,
    get_criterion,
    get_or_create_scoring_run,
    has_success_payload,
)
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_audit(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_get_or_create_scoring_run_creates_a_new_run(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)

    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)

    assert scoring_run.id is not None
    assert scoring_run.audit_id == audit.id
    assert scoring_run.methodology_version_id == methodology_version.id


def test_get_or_create_scoring_run_reuses_existing(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)

    first = get_or_create_scoring_run(db_session, audit, methodology_version)
    second = get_or_create_scoring_run(db_session, audit, methodology_version)

    assert first.id == second.id


def test_get_criterion_finds_a_seeded_criterion(db_session):
    methodology_version = seed_taxonomy(db_session)

    criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Dependency direction / circularity",
    )

    assert criterion.name == "Dependency direction / circularity"


def test_get_criterion_raises_when_not_found(db_session):
    methodology_version = seed_taxonomy(db_session)

    with pytest.raises(CriterionNotFoundError):
        get_criterion(db_session, methodology_version.id, "Nonexistent", "Nope")


def _tool_result(raw_output, exit_code=0):
    return ToolResult(
        audit_id=1,
        subproject_path=".",
        tool_name="stub",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=exit_code,
        duration_ms=1,
    )


def test_has_success_payload_accepts_an_empty_payload_list():
    assert has_success_payload(_tool_result({"findings": []}), "findings") is True


def test_has_success_payload_rejects_the_orchestrator_crash_record():
    crashed = _tool_result({"error": "timed out"}, exit_code=-1)

    assert has_success_payload(crashed, "findings") is False


def test_has_success_payload_rejects_a_missing_payload_key():
    assert has_success_payload(_tool_result({"stdout": "", "stderr": ""}), "findings") is False


def test_has_success_payload_rejects_a_runner_reported_error():
    failed = _tool_result({"error": "boom", "vulnerabilities": []})

    assert has_success_payload(failed, "vulnerabilities") is False


def test_add_finding_with_recommendation_links_a_recommendation_to_the_finding(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Architectural documentation present",
    )
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.LOW,
        description="stub finding",
        confidence=Confidence.MEDIUM,
        status=FindingStatus.OPEN,
        human_verdict=HumanVerdict.UNREVIEWED,
    )

    add_finding_with_recommendation(db_session, finding, "Do the thing that fixes it.")
    db_session.commit()

    recommendation = db_session.exec(
        select(Recommendation).where(Recommendation.finding_id == finding.id)
    ).one()
    assert recommendation.text == "Do the thing that fixes it."
