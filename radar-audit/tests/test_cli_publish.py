from radar_audit import cli
from radar_audit.cli import app
from radar_core.db import get_engine
from radar_core.models.audit import Audit
from radar_core.models.methodology import MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun
from radar_core.publishing import DirtyAuditError
from sqlmodel import Session
from typer.testing import CliRunner

from tests.test_cli_score_report import _migrate

runner = CliRunner()


def _seed_scored_repository(db_path, name="sample-repo"):
    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        repository = Repository(name=name, path=f"/tmp/{name}")
        version = MethodologyVersion(version_label="v-test")
        session.add_all([repository, version])
        session.commit()
        audit = Audit(repository_id=repository.id, commit_sha="f" * 40)
        session.add(audit)
        session.commit()
        session.add(
            ScoringRun(audit_id=audit.id, methodology_version_id=version.id, global_score=5.0)
        )
        session.commit()
    engine.dispose()


def test_publish_prints_the_public_url(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)
    _seed_scored_repository(db_path)
    published = []

    def fake_publish(session, scoring_run):
        published.append(scoring_run.id)
        return "https://radar.example.dev/u/ada/sample-repo"

    monkeypatch.setattr(cli, "publish_scoring_run", fake_publish)

    result = runner.invoke(app, ["publish", "sample-repo"])

    assert result.exit_code == 0
    assert "https://radar.example.dev/u/ada/sample-repo" in result.stdout
    assert len(published) == 1


def test_publish_fails_cleanly_for_an_unknown_repository(tmp_path, monkeypatch):
    _migrate(tmp_path / "test.db", monkeypatch)

    result = runner.invoke(app, ["publish", "not-a-real-repo"])

    assert result.exit_code == 1
    assert "not-a-real-repo" in result.stderr


def test_publish_fails_cleanly_for_an_unscored_repository(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)
    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        session.add(Repository(name="fresh", path="/tmp/fresh"))
        session.commit()
    engine.dispose()

    result = runner.invoke(app, ["publish", "fresh"])

    assert result.exit_code == 1
    assert "radar-audit score fresh" in result.stderr


def test_publish_reports_a_refusal_without_a_traceback(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)
    _seed_scored_repository(db_path)

    def fake_publish(session, scoring_run):
        raise DirtyAuditError("The latest audit scored a modified working tree")

    monkeypatch.setattr(cli, "publish_scoring_run", fake_publish)

    result = runner.invoke(app, ["publish", "sample-repo"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "modified working tree" in result.stderr
