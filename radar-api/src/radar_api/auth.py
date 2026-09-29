from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from radar_api.config import MissingApiKeyError, get_api_key


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    try:
        expected = get_api_key()
    except MissingApiKeyError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
        ) from err
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
        )
