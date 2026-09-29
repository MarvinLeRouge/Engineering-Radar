from __future__ import annotations

import os


class MissingDatabaseUrlError(RuntimeError):
    """Raised when RADAR_DATABASE_URL is not set."""


class MissingApiKeyError(RuntimeError):
    """Raised when RADAR_API_KEY is not set."""


def get_database_url() -> str:
    url = os.environ.get("RADAR_DATABASE_URL")
    if not url:
        raise MissingDatabaseUrlError(
            "RADAR_DATABASE_URL must be set explicitly; radar-api never assumes "
            "a default database location."
        )
    return url


def get_api_key() -> str:
    key = os.environ.get("RADAR_API_KEY")
    if not key:
        raise MissingApiKeyError(
            "RADAR_API_KEY must be set explicitly; radar-api never assumes a default API key."
        )
    return key
