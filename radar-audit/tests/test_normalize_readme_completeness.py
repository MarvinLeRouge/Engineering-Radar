from radar_audit.normalizers.readme_completeness import normalize_readme_completeness
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
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
        "README completeness",
    )
    return scoring_run, criterion


def test_no_readme_scores_zero_and_creates_a_finding(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 0.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert "no README" in findings[0].description


def test_readme_with_no_standard_sections_scores_four(db_session, tmp_path):
    (tmp_path / "README.md").write_text("# My Project\n\nSome prose, no section headers.\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 4.0


def test_readme_with_two_of_three_sections_scores_seven(db_session, tmp_path):
    (tmp_path / "README.md").write_text(
        "# My Project\n\n## Setup\n\ninstall steps\n\n## Usage\n\nhow to run\n"
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 7.0


def test_readme_with_all_three_sections_scores_ten(db_session, tmp_path):
    (tmp_path / "README.md").write_text(
        "# My Project\n\n## Setup\n\ninstall steps\n\n"
        "## Usage\n\nhow to run\n\n## Architecture Overview\n\nhow it works\n"
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 0


def test_readme_md_uppercase_variant_is_detected(db_session, tmp_path):
    (tmp_path / "README.MD").write_text(
        "# My Project\n\n## Install\n\nsteps\n\n## Usage\n\nsteps\n\n## Architecture\n\nsteps\n"
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_readme_mixed_case_variant_is_detected(db_session, tmp_path):
    (tmp_path / "Readme.md").write_text("# My Project\n\nprose only\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 4.0


def test_generic_overview_header_alone_does_not_count_as_architecture(db_session, tmp_path):
    (tmp_path / "README.md").write_text(
        "# My Project\n\n## Setup\n\ninstall steps\n\n## Usage\n\nhow to run\n\n"
        "## Overview\n\na product overview, not an architecture section\n"
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_readme_completeness(db_session, scoring_run, criterion, [])

    assert score.value == 7.0
