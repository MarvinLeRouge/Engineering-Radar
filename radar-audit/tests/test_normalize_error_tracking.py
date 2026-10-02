from radar_audit.normalizers.error_tracking import normalize_error_tracking
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
        "Observability / operations",
        "Error tracking integration",
    )
    return scoring_run, criterion


def test_no_sentry_dependency_scores_zero(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_error_tracking(db_session, scoring_run, criterion, [])

    assert score.value == 0.0


def test_sentry_dependency_present_but_no_init_call_found_scores_five(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["sentry-sdk>=2.0"]\n')
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_error_tracking(db_session, scoring_run, criterion, [])

    assert score.value == 5.0


def test_sentry_init_wired_via_env_var_scores_ten(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["sentry-sdk>=2.0"]\n')
    (tmp_path / "main.py").write_text(
        "import os\nimport sentry_sdk\n\n"
        'sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=1.0)\n'
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_error_tracking(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_sentry_init_wired_via_placeholder_literal_scores_five(db_session, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["sentry-sdk>=2.0"]\n')
    (tmp_path / "main.py").write_text(
        'import sentry_sdk\n\nsentry_sdk.init(dsn="https://examplePublicKey@o0.ingest.sentry.io/0")\n'
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_error_tracking(db_session, scoring_run, criterion, [])

    assert score.value == 5.0


def test_sentry_js_dependency_with_env_var_init_scores_ten(db_session, tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"@sentry/node": "^8.0.0"}}')
    (tmp_path / "index.js").write_text(
        "Sentry.init({ dsn: process.env.SENTRY_DSN, tracesSampleRate: 1.0 });\n"
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_error_tracking(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
