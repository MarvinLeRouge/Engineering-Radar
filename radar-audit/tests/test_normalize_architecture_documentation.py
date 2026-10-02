from radar_audit.normalizers.architecture_documentation import (
    normalize_architecture_documentation,
)
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session, repo_path):
    repo = Repository(name="repo", path=str(repo_path))
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
        db_session,
        methodology_version.id,
        "Documentation",
        "Architecture documentation",
    )
    return scoring_run, criterion


def _design_doc_tool_result(found_path, non_blank_lines, exit_code=0):
    return ToolResult(
        tool_name="design-doc-presence",
        tool_version="1.0.0",
        command="filesystem-check",
        raw_output={"found_path": found_path, "non_blank_lines": non_blank_lines},
        exit_code=exit_code,
        duration_ms=1,
    )


def test_no_design_doc_tool_result_returns_none(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_architecture_documentation(db_session, scoring_run, criterion, [])

    assert score is None


def test_crashed_tool_result_returns_none(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)
    tool_result = _design_doc_tool_result(None, 0, exit_code=-1)

    score = normalize_architecture_documentation(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_no_doc_found_scores_zero_and_creates_a_finding(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)
    tool_result = _design_doc_tool_result(None, 0)

    score = normalize_architecture_documentation(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 0.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_trivial_doc_scores_six(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)
    tool_result = _design_doc_tool_result("DESIGN.md", 5)

    score = normalize_architecture_documentation(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0


def test_substantial_doc_scores_ten(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)
    tool_result = _design_doc_tool_result("DESIGN.md", 40)

    score = normalize_architecture_documentation(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 0
