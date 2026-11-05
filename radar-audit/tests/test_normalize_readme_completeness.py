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


def _score_readme(db_session, tmp_path, text):
    (tmp_path / "README.md").write_text(text)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)
    return normalize_readme_completeness(db_session, scoring_run, criterion, [])


def test_a_comment_inside_a_code_block_is_not_a_section_header(db_session, tmp_path):
    score = _score_readme(
        db_session,
        tmp_path,
        "# My Project\n\n## Architecture\n\ntext\n\n"
        "```bash\n# install deps\n# usage example\n```\n",
    )

    assert score.value == 7.0


def test_quick_start_counts_as_both_setup_and_usage(db_session, tmp_path):
    score = _score_readme(
        db_session, tmp_path, "# My Project\n\n## Quick start\n\nsteps\n\n## Architecture\n\nx\n"
    )

    assert score.value == 10.0


def test_common_section_synonyms_are_recognized(db_session, tmp_path):
    score = _score_readme(
        db_session,
        tmp_path,
        "# P\n\n## Installation & Launch\n\nsteps\n\n## How it works\n\nx\n",
    )

    assert score.value == 10.0


def test_a_tests_heading_is_not_usage(db_session, tmp_path):
    score = _score_readme(
        db_session,
        tmp_path,
        "# P\n\n## Installation\n\nx\n\n## Running tests\n\nx\n\n## Architecture\n\nx\n",
    )

    assert score.value == 7.0


def test_a_link_to_a_local_doc_credits_the_sections_its_line_names(db_session, tmp_path):
    (tmp_path / "docs").mkdir()
    for name in ("architecture.md", "dev.md", "operations.md"):
        (tmp_path / "docs" / name).write_text("content\n")

    score = _score_readme(
        db_session,
        tmp_path,
        "# P\n\n## Documentation\n\n"
        "- [Architecture](docs/architecture.md): overview\n"
        "- [Developer guide](docs/dev.md): local setup, tests\n"
        "- [Operations](docs/operations.md): running the system locally\n",
    )

    assert score.value == 10.0


def test_a_link_to_a_missing_or_remote_doc_credits_nothing(db_session, tmp_path):
    score = _score_readme(
        db_session,
        tmp_path,
        "# P\n\n- [Setup guide](docs/missing.md): installation\n"
        "- [Usage](https://example.com/usage.md): usage\n",
    )

    assert score.value == 4.0
