from radar_audit.normalizers.container_build_hardening import (
    normalize_container_build_hardening,
)
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "DevOps / CI-CD", "Container build hardening"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output, exit_code=0):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="hadolint",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=exit_code,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_hadolint_tool_result_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [])

    assert score is None


def test_zero_findings_across_all_dockerfiles_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {"dockerfiles": [{"path": "Dockerfile", "findings": []}]},
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_four_findings_across_dockerfiles_scores_six(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {
                    "path": "Dockerfile",
                    "findings": [
                        {"code": "DL3008", "message": "a"},
                        {"code": "DL3009", "message": "b"},
                    ],
                },
                {
                    "path": "backend/Dockerfile",
                    "findings": [
                        {"code": "DL3002", "message": "c"},
                        {"code": "DL3007", "message": "d"},
                    ],
                },
            ]
        },
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0


def test_does_not_duplicate_findings_already_created_by_criterion_4_5(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {"dockerfiles": [{"path": "Dockerfile", "findings": [{"code": "DL3008", "message": "a"}]}]},
    )

    normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 0


def test_failed_dockerfile_entry_excluded_from_the_count(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "error": "Cannot connect to the Docker daemon"},
                {"path": "backend/Dockerfile", "findings": []},
            ]
        },
        exit_code=1,
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_orchestrator_crash_record_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    crashed = _make_tool_result(
        db_session, audit, {"error": "Command 'docker' timed out after 120 seconds"}, exit_code=-1
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [crashed])

    assert score is None


def test_no_dockerfiles_found_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"dockerfiles": []})

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_all_dockerfile_entries_errored_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {"dockerfiles": [{"path": "Dockerfile", "error": "could not lint"}]},
        exit_code=1,
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None
