import pytest
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.orchestrator import execute_audit
from radar_audit.report import NoScoringRunFoundError, render_report, write_report
from radar_audit.scoring import RepositoryNotFoundError, score_repository
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence, FindingSeverity, ScoreLevel
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score

from tests.git_helpers import init_git_repo


def _scored_repo(db_session, tmp_path, name="repo"):
    repo_path = tmp_path / name
    init_git_repo(
        repo_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=[name])
    execute_audit(db_session, config, name, DEFAULT_RUNNERS)
    return score_repository(db_session, name)


def _bare_scoring_run(db_session, name="repo"):
    # A scoring run with no normalizer-produced data, for tests that assert on
    # hand-crafted Score/Finding rows rather than real tool output.
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    return get_or_create_scoring_run(db_session, audit, methodology_version)


def test_render_report_raises_when_repository_unknown(db_session):
    with pytest.raises(RepositoryNotFoundError):
        render_report(db_session, "does-not-exist")


def test_render_report_raises_when_no_score_exists(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    with pytest.raises(NoScoringRunFoundError):
        render_report(db_session, "repo")


def test_render_report_shows_scored_categories_and_not_yet_audited_placeholders(
    db_session, tmp_path
):
    _scored_repo(db_session, tmp_path)

    markdown = render_report(db_session, "repo")

    assert "# Report: repo" in markdown
    assert "Architecture & design" in markdown
    assert "Not yet audited" in markdown  # category 4 (Security) has no data yet
    assert "not scored this run" in markdown  # 1.4 has no normalizer


def test_render_report_shows_na_reason_for_not_applicable_criterion(db_session):
    scoring_run = _bare_scoring_run(db_session)
    criterion = get_criterion(
        db_session,
        scoring_run.methodology_version_id,
        "Maintainability",
        "Documentation-in-code (docstring/comment coverage)",
    )
    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=0.0,
        confidence=Confidence.HIGH,
        na_reason="No documentation-coverage tool available for JS/TS",
    )
    db_session.add(score)
    db_session.commit()

    markdown = render_report(db_session, "repo")

    assert "N/A" in markdown
    assert "No documentation-coverage tool available for JS/TS" in markdown
    assert "0.0/10" not in markdown


def test_render_report_shows_findings_under_their_criterion(db_session):
    scoring_run = _bare_scoring_run(db_session)
    criterion = get_criterion(
        db_session,
        scoring_run.methodology_version_id,
        "Architecture & design",
        "Architectural documentation present",
    )
    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=4.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(score)
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.LOW,
        description="no architectural documentation found",
        file="DESIGN.md",
        line=12,
        confidence=Confidence.MEDIUM,
    )
    db_session.add(finding)
    db_session.commit()

    markdown = render_report(db_session, "repo")

    assert "no architectural documentation found" in markdown
    assert "LOW" in markdown
    assert "DESIGN.md:12" in markdown


def test_write_report_creates_file_under_repo_named_subdir(db_session, tmp_path):
    _scored_repo(db_session, tmp_path)
    markdown = render_report(db_session, "repo")

    output_dir = tmp_path / "reports"
    written_path = write_report(markdown, "repo", output_dir)

    assert written_path == output_dir / "repo" / "latest.md"
    assert written_path.read_text() == markdown
