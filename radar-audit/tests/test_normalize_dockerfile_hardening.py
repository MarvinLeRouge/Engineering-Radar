from radar_audit.normalizers.dockerfile_hardening import normalize_dockerfile_hardening
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import FindingSeverity
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding, Recommendation
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
        db_session, methodology_version.id, "Security", "Dockerfile hardening"
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


def test_no_dockerfiles_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"dockerfiles": []})

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_one_clean_dockerfile_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"dockerfiles": [{"path": "Dockerfile", "findings": []}]}
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_a_single_info_finding_scores_six_not_zero(db_session):
    """A lone cosmetic finding must not collapse the whole criterion to the
    worst possible score -- this is the exact miscalibration FIX-005 corrects.
    """
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {
                    "path": "Dockerfile",
                    "findings": [
                        {
                            "code": "DL3066",
                            "column": 1,
                            "file": "-",
                            "level": "info",
                            "line": 9,
                            "message": "Non-numeric user-id may not be resolvable",
                        }
                    ],
                }
            ]
        },
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0


def test_worst_severity_present_drives_the_score_not_finding_count(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {
                    "path": "backend/Dockerfile",
                    "findings": [
                        {
                            "code": "DL3008",
                            "column": 1,
                            "file": "-",
                            "level": "warning",
                            "line": 14,
                            "message": "Pin versions in apt get install",
                        },
                        {
                            "code": "DL3066",
                            "column": 1,
                            "file": "-",
                            "level": "info",
                            "line": 49,
                            "message": "Non-numeric user-id may not be resolvable",
                        },
                    ],
                },
                {
                    "path": "frontend/Dockerfile",
                    "findings": [
                        {
                            "code": "DL3001",
                            "column": 1,
                            "file": "-",
                            "level": "error",
                            "line": 3,
                            "message": "Some broken rule",
                        }
                    ],
                },
            ]
        },
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    # Worst across both Dockerfiles is the single "error"-level finding -> HIGH.
    assert score.value == 4.0


def test_maps_hadolint_level_onto_finding_severity_and_creates_one_finding_per_entry(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {
                    "path": "backend/Dockerfile",
                    "findings": [
                        {
                            "code": "DL3008",
                            "column": 1,
                            "file": "-",
                            "level": "warning",
                            "line": 14,
                            "message": "Pin versions in apt get install",
                        },
                        {
                            "code": "DL3066",
                            "column": 1,
                            "file": "-",
                            "level": "info",
                            "line": 49,
                            "message": "Non-numeric user-id may not be resolvable",
                        },
                    ],
                }
            ]
        },
    )

    normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(
        select(Finding).where(Finding.criterion_id == criterion.id).order_by(Finding.line)  # type: ignore[arg-type]
    ).all()
    assert len(findings) == 2
    assert findings[0].line == 14
    assert findings[0].severity == FindingSeverity.MEDIUM
    assert findings[1].line == 49
    assert findings[1].severity == FindingSeverity.LOW
    recommendations = db_session.exec(
        select(Recommendation).where(Recommendation.finding_id == findings[0].id)
    ).all()
    assert len(recommendations) == 1


def test_orchestrator_crash_record_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    crashed = _make_tool_result(
        db_session, audit, {"error": "Command 'docker' timed out after 120 seconds"}, exit_code=-1
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [crashed])

    assert score is None


def test_all_dockerfiles_failed_to_lint_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {"dockerfiles": [{"path": "Dockerfile", "error": "Cannot connect to the Docker daemon"}]},
        exit_code=1,
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_failed_dockerfile_is_excluded_and_the_other_one_scores_normally(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "error": "Cannot connect to the Docker daemon"},
                {"path": "frontend/Dockerfile", "findings": []},
            ]
        },
        exit_code=1,
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_two_hits_same_rule_same_file_get_different_fingerprints(db_session, tmp_path):
    (tmp_path / "Dockerfile").write_text(
        "FROM ubuntu\nRUN apt-get install curl\nRUN apt-get install wget\n"
    )
    repo = Repository(name="repo", path=str(tmp_path))
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
        db_session, methodology_version.id, "Security", "Dockerfile hardening"
    )
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {
                    "path": "Dockerfile",
                    "findings": [
                        {
                            "code": "DL3008",
                            "level": "warning",
                            "message": "Pin versions in apt-get install",
                            "line": 2,
                        },
                        {
                            "code": "DL3008",
                            "level": "warning",
                            "message": "Pin versions in apt-get install",
                            "line": 3,
                        },
                    ],
                }
            ]
        },
    )

    normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 2
    assert findings[0].fingerprint != findings[1].fingerprint
