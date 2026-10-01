from radar_audit.normalizers.ci_health import normalize_ci_health
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
        db_session, methodology_version.id, "DevOps / CI-CD", "CI presence & health"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output, exit_code=0):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="actionlint",
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


def test_no_usable_tool_result_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"error": "no project was found"}, exit_code=3
    )

    score = normalize_ci_health(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_clean_workflow_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"findings": []})

    score = normalize_ci_health(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_two_findings_scores_eight_and_creates_findings(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "message": "shellcheck issue",
                    "filepath": ".github/workflows/ci.yml",
                    "line": 8,
                    "kind": "shellcheck",
                },
                {
                    "message": "another issue",
                    "filepath": ".github/workflows/ci.yml",
                    "line": 10,
                    "kind": "syntax-check",
                },
            ]
        },
        exit_code=1,
    )

    score = normalize_ci_health(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 8.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 2
    assert findings[0].file == ".github/workflows/ci.yml"
    assert findings[0].line == 8
