from radar_audit.normalizers.health_check import normalize_health_check
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
        "Health-check endpoint",
    )
    return scoring_run, criterion


def test_no_prod_compose_file_scores_na(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_health_check(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None
    assert score.value == 0.0


def test_long_lived_service_with_no_health_route_scores_zero(db_session, tmp_path):
    (tmp_path / "docker-compose.prod.yml").write_text("services:\n  app:\n    image: app\n")
    (tmp_path / "main.py").write_text("def handler():\n    return 'ok'\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_health_check(db_session, scoring_run, criterion, [])

    assert score.na_reason is None
    assert score.value == 0.0


def test_long_lived_service_with_health_route_scores_ten(db_session, tmp_path):
    (tmp_path / "docker-compose.prod.yml").write_text("services:\n  app:\n    image: app\n")
    (tmp_path / "main.py").write_text(
        '@app.get("/health")\ndef health():\n    return {"status": "ok"}\n'
    )
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_health_check(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None


def test_healthz_variant_is_detected(db_session, tmp_path):
    (tmp_path / "docker-compose.prod.yml").write_text("services:\n  app:\n    image: app\n")
    (tmp_path / "index.js").write_text("app.get('/healthz', (req, res) => res.sendStatus(200));\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_health_check(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
