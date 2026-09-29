from radar_core.models.audit import Audit
from radar_core.models.methodology import MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_scoring_run(db_session, repository, global_score):
    audit = Audit(repository_id=repository.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}-{global_score}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(
        audit_id=audit.id,
        methodology_version_id=methodology_version.id,
        global_score=global_score,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)
    return scoring_run


def test_list_repositories_returns_not_yet_audited_when_no_scoring_run(client, db_session):
    _make_repository(db_session, "repo-a")

    response = client.get("/repositories")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["audit_status"] == "not_yet_audited"
    assert body[0]["global_score"] is None


def test_list_repositories_returns_global_score_when_scored(client, db_session):
    repo = _make_repository(db_session, "repo-b")
    _make_scoring_run(db_session, repo, global_score=7.5)

    response = client.get("/repositories")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["audit_status"] == "scored"
    assert body[0]["global_score"] == 7.5


def test_get_repository_returns_404_when_missing(client):
    response = client.get("/repositories/999")

    assert response.status_code == 404


def test_get_repository_returns_detail(client, db_session):
    repo = _make_repository(db_session, "repo-c")

    response = client.get(f"/repositories/{repo.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "repo-c"
