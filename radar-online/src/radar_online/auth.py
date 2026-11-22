"""API key authentication for radar-online's write endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, col, select

from radar_online.dependencies import get_db_session
from radar_online.models import ApiKey, User, UserStatus
from radar_online.tokens import hash_secret


def require_user(
    session: Annotated[Session, Depends(get_db_session)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> User:
    """Return the ACTIVE user owning the X-API-Key, or raise a 401.

    Missing, unknown, revoked and inactive-owner keys all get the same answer, so a
    caller learns nothing about which keys or accounts exist. Only the key's hash is
    looked up; the key itself is never logged.
    """
    user = None
    if x_api_key:
        user = session.exec(
            select(User)
            .join(ApiKey, col(ApiKey.user_id) == col(User.id))
            .where(
                ApiKey.key_hash == hash_secret(x_api_key),
                col(ApiKey.revoked_at).is_(None),
                User.status == UserStatus.ACTIVE,
            )
        ).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key"
        )
    return user
