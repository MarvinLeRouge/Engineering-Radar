"""Environment-based configuration accessors for radar-online."""

from __future__ import annotations

import os


class MissingDatabaseUrlError(RuntimeError):
    """Raised when RADAR_ONLINE_DATABASE_URL is not set."""


def get_database_url() -> str:
    """Return RADAR_ONLINE_DATABASE_URL, raising MissingDatabaseUrlError if it is unset or empty."""
    url = os.environ.get("RADAR_ONLINE_DATABASE_URL")
    if not url:
        raise MissingDatabaseUrlError(
            "RADAR_ONLINE_DATABASE_URL must be set explicitly; radar-online never assumes "
            "a default database location."
        )
    return url
