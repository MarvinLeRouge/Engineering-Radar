"""Regression: SQLite caps bound parameters per statement (32766 by default).

Summit-Stats has over 60,000 findings in one scoring run; every query that bound
one parameter per finding id crashed with "too many SQL variables". The limit is
lowered on the test connection so a handful of findings reproduces it.
"""

import sqlite3

import pytest
from radar_audit.normalizers.shared import (
    add_finding_with_recommendation,
    get_criterion,
    get_or_create_scoring_run,
)
from radar_audit.orchestrator import _cleanup_stale_tool_results
from radar_audit.report import render_report
from radar_audit.roadmap_promotion import promote_improvement_tasks
from radar_audit.scoring import score_repository
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence, FindingSeverity
from radar_core.finding_fingerprint import compute_fingerprint
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from sqlmodel import select

_VARIABLE_LIMIT = 50
_FINDINGS = 80


@pytest.fixture
def tight_session(db_session):
    """The test session, with SQLite allowed only _VARIABLE_LIMIT bound parameters."""
    raw = db_session.connection().connection.driver_connection
    raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, _VARIABLE_LIMIT)
    return db_session


def _audit_with_findings(session, tmp_path, tool_result=False):
    from radar_core.models.repository import Repository

    repo = Repository(name="big", path=str(tmp_path))
    session.add(repo)
    session.commit()
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    session.add(audit)
    session.commit()
    version = seed_taxonomy(session)
    run = get_or_create_scoring_run(session, audit, version)
    criterion = get_criterion(session, version.id, "Code quality", "Type-checking pass")
    result = None
    if tool_result:
        result = ToolResult(
            audit_id=audit.id,
            subproject_path=".",
            tool_name="mypy",
            tool_version="1.0.0",
            command="mypy",
            raw_output={},
            exit_code=1,
            duration_ms=1,
        )
        session.add(result)
        session.commit()
    for i in range(_FINDINGS):
        description = f"type error {i}"
        add_finding_with_recommendation(
            session,
            Finding(
                scoring_run_id=run.id,
                criterion_id=criterion.id,
                tool_result_id=result.id if result else None,
                severity=FindingSeverity.LOW,
                description=description,
                file=f"src/module_{i}.py",
                fingerprint=compute_fingerprint(
                    criterion.id, FindingSeverity.LOW, f"src/module_{i}.py", description
                ),
                confidence=Confidence.HIGH,
            ),
            "Fix this type error.",
        )
    session.commit()
    return audit, run


def test_rescoring_a_run_with_many_findings_succeeds(tight_session, tmp_path):
    _audit_with_findings(tight_session, tmp_path)

    score_repository(tight_session, "big")


def test_promoting_many_findings_to_the_roadmap_succeeds(tight_session, tmp_path):
    _, run = _audit_with_findings(tight_session, tmp_path)

    promote_improvement_tasks(tight_session, run)


def test_rendering_the_report_of_many_findings_succeeds(tight_session, tmp_path):
    _audit_with_findings(tight_session, tmp_path)

    assert "type error 79" in render_report(tight_session, "big")


def test_cleaning_up_many_stale_findings_before_a_rerun_succeeds(tight_session, tmp_path):
    audit, _ = _audit_with_findings(tight_session, tmp_path, tool_result=True)

    _cleanup_stale_tool_results(tight_session, audit)
    tight_session.commit()

    assert tight_session.exec(select(Finding)).all() == []
