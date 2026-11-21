from radar_online.cli import app
from radar_online.models import ApiKey
from radar_online.tokens import hash_secret
from sqlmodel import select
from typer.testing import CliRunner

_ARGS = ["create-account", "--email", "ada@example.com", "--display-name", "Ada", "--slug", "ada"]


def test_create_account_prints_the_key_once(session, database_url, monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)

    result = CliRunner().invoke(app, _ARGS)

    assert result.exit_code == 0
    key_hash = session.exec(select(ApiKey.key_hash)).one()
    printed_keys = [line for line in result.stdout.split() if hash_secret(line) == key_hash]
    assert len(printed_keys) == 1
    assert "shown once" in result.stdout


def test_create_account_fails_on_a_duplicate(database_url, monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)
    CliRunner().invoke(app, _ARGS)

    result = CliRunner().invoke(app, _ARGS)

    assert result.exit_code == 1
    assert "already" in result.output
