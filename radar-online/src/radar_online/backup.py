"""Consistent copies of radar-online's SQLite database, with rotation (CHORE-011)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_PREFIX = "radar-online-"
_SQLITE_URL_PREFIX = "sqlite:///"
DEFAULT_KEEP = 14


class BackupError(RuntimeError):
    """Raised when the database cannot be backed up."""


def backup_database(
    database_url: str, target_dir: Path, now: datetime | None = None, keep: int = DEFAULT_KEEP
) -> Path:
    """Copy the database into `target_dir` and keep only its `keep` most recent backups.

    Uses SQLite's online backup API, so the copy is consistent even while the service
    writes, without needing the sqlite3 binary in the image.

    Raises:
        BackupError: the URL is not a SQLite file URL, or the database file is missing.
    """
    if not database_url.startswith(_SQLITE_URL_PREFIX):
        raise BackupError("Only a SQLite database (sqlite:///...) can be backed up")
    source_path = Path(database_url.removeprefix(_SQLITE_URL_PREFIX))
    if not source_path.is_file():
        raise BackupError(f"The database {source_path} does not exist")

    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"{_PREFIX}{stamp}.db"
    # mode=ro: a backup never creates or changes the live database.
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()

    for old in sorted(target_dir.glob(f"{_PREFIX}*.db"))[:-keep]:
        old.unlink()
    return target
