from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.traefik_parity import normalize_traefik_parity
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
        "DevOps / CI-CD",
        "Reverse proxy / local-prod environment parity (Traefik)",
    )
    return scoring_run, criterion


_TRAEFIK_LABELS = """\
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app.rule=Host(`example.local`)"
"""


def test_no_local_compose_file_returns_none(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score is None


def test_no_prod_candidate_found_scores_na(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(f"services:\n  app:\n{_TRAEFIK_LABELS}")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_no_traefik_anywhere_scores_na(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services:\n  app:\n    image: nginx\n")
    (tmp_path / "docker-compose.prod.yml").write_text("services:\n  app:\n    image: nginx\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_full_parity_scores_ten(db_session, tmp_path):
    compose = (
        f"services:\n  backend:\n{_TRAEFIK_LABELS}  frontend:\n{_TRAEFIK_LABELS}"
        "  db:\n    image: postgres\n"
    )
    (tmp_path / "docker-compose.yml").write_text(compose)
    (tmp_path / "docker-compose.prod.yml").write_text(compose)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None


def test_partial_parity_scores_between_zero_and_ten_and_creates_a_finding(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(
        f"services:\n  backend:\n{_TRAEFIK_LABELS}  frontend:\n{_TRAEFIK_LABELS}"
    )
    (tmp_path / "docker-compose.prod.yml").write_text(f"services:\n  backend:\n{_TRAEFIK_LABELS}")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 5.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert "frontend" in findings[0].description


def test_malformed_compose_file_treated_as_absent(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(": not: valid: yaml: [")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score is None


def test_prod_filename_candidate_order_prefers_docker_compose_prod(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(f"services:\n  app:\n{_TRAEFIK_LABELS}")
    (tmp_path / "docker-compose.prod.yml").write_text(f"services:\n  app:\n{_TRAEFIK_LABELS}")
    (tmp_path / "compose.prod.yaml").write_text("services:\n  app:\n    image: nginx\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_dict_form_labels_with_unquoted_boolean_detected_as_traefik_routed(db_session, tmp_path):
    compose = "services:\n  app:\n    labels:\n      traefik.enable: true\n"
    (tmp_path / "docker-compose.yml").write_text(compose)
    (tmp_path / "docker-compose.prod.yml").write_text(compose)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None


def test_dict_form_labels_with_quoted_string_boolean_detected_as_traefik_routed(
    db_session, tmp_path
):
    compose = 'services:\n  app:\n    labels:\n      traefik.enable: "true"\n'
    (tmp_path / "docker-compose.yml").write_text(compose)
    (tmp_path / "docker-compose.prod.yml").write_text(compose)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None
