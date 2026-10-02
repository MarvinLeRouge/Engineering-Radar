from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.structured_logging import normalize_structured_logging
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository


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
        "Observability / operations",
        "Structured logging",
    )
    return scoring_run, criterion


def test_no_manifest_at_all_scores_four(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 4.0
    assert score.na_reason is None


def test_structlog_in_pyproject_toml_scores_ten(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["structlog>=24.1"]\n')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_loguru_in_requirements_txt_scores_ten(db_session, tmp_path):
    (tmp_path / "requirements.txt").write_text("loguru==0.7.2\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_winston_in_package_json_scores_ten(db_session, tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"winston": "^3.13.0"}}')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_pino_in_package_json_dev_dependencies_scores_ten(db_session, tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies": {"pino": "^9.0.0"}}')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_unrelated_python_dependency_scores_four(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi>=0.110"]\n')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 4.0


def test_structured_logging_in_a_backend_subproject_directory_scores_ten(db_session, tmp_path):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "requirements.txt").write_text("structlog==24.1.0\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_structured_logging(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
