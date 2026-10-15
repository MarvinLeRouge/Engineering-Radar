from radar_audit.normalizers.api_documentation import normalize_api_documentation
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
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
        "Documentation",
        "API documentation",
    )
    return scoring_run, criterion


def test_no_manifest_at_all_scores_na(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None
    assert score.value == 0.0


def test_fastapi_in_pyproject_toml_scores_ten(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi>=0.110"]\n')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None


def test_fastapi_in_requirements_txt_scores_ten(db_session, tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi==0.110.0\nuvicorn==0.30.0\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_python_manifest_without_fastapi_scores_na(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["flask>=3.0"]\n')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_l5_swagger_in_composer_require_scores_ten(db_session, tmp_path):
    (tmp_path / "composer.json").write_text('{"require": {"darkaonline/l5-swagger": "^8.0"}}')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None


def test_l5_swagger_in_composer_require_dev_scores_ten(db_session, tmp_path):
    (tmp_path / "composer.json").write_text('{"require-dev": {"darkaonline/l5-swagger": "^8.0"}}')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_composer_without_l5_swagger_scores_na(db_session, tmp_path):
    (tmp_path / "composer.json").write_text('{"require": {"laravel/framework": "^11.0"}}')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_malformed_composer_json_treated_as_no_match(db_session, tmp_path):
    (tmp_path / "composer.json").write_text("{not valid json")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_fastapi_mentioned_only_in_prose_does_not_score_ten(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'description = "A lightweight alternative to fastapi"\n'
        'dependencies = ["flask>=3.0"]\n'
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_fastapi_in_a_backend_subproject_directory_scores_ten(db_session, tmp_path):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "requirements.txt").write_text("fastapi==0.141.1\n")
    (tmp_path / "frontend").mkdir()
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_api_documentation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None
