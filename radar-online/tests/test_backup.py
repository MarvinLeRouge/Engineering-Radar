import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from radar_online.backup import BackupError, backup_database
from radar_online.cli import app
from typer.testing import CliRunner


def _db_path(database_url):
    return database_url.removeprefix("sqlite:///")


def test_backup_is_a_readable_copy_of_the_database(database_url, tmp_path):
    target = tmp_path / "backups"

    written = backup_database(database_url, target, now=datetime(2026, 11, 22, 3, 0, tzinfo=UTC))

    assert written == target / "radar-online-20261122T030000Z.db"
    tables = {row[0] for row in sqlite3.connect(written).execute("select name from sqlite_master")}
    assert "published_report" in tables


def test_only_the_most_recent_backups_are_kept(database_url, tmp_path):
    start = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)
    for day in range(16):
        backup_database(database_url, tmp_path, now=start + timedelta(days=day), keep=14)

    kept = sorted(path.name for path in tmp_path.glob("radar-online-*.db"))

    assert len(kept) == 14
    assert kept[0] == "radar-online-20261103T030000Z.db"
    assert kept[-1] == "radar-online-20261116T030000Z.db"


def test_other_files_in_the_folder_are_left_alone(database_url, tmp_path):
    (tmp_path / "notes.txt").write_text("keep me")

    backup_database(database_url, tmp_path, keep=1)
    backup_database(database_url, tmp_path, now=datetime(2030, 1, 1, tzinfo=UTC), keep=1)

    assert (tmp_path / "notes.txt").read_text() == "keep me"


def test_only_sqlite_urls_can_be_backed_up(tmp_path):
    with pytest.raises(BackupError, match="SQLite"):
        backup_database("postgresql://db/radar", tmp_path)


def test_missing_database_is_reported_without_creating_one(tmp_path):
    missing = tmp_path / "missing.db"

    with pytest.raises(BackupError, match="does not exist"):
        backup_database(f"sqlite:///{missing}", tmp_path / "backups")

    assert not missing.exists()


def test_backup_command_prints_the_written_file(database_url, tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_ONLINE_DATABASE_URL", database_url)

    result = CliRunner().invoke(app, ["backup", str(tmp_path)])

    assert result.exit_code == 0
    assert str(tmp_path) in result.stdout
    assert len(list(tmp_path.glob("radar-online-*.db"))) == 1
