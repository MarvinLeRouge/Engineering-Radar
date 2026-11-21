"""Account creation by the admin, before the email registration flow exists (FEAT-050)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from radar_core.db import persisted_id
from sqlmodel import Session, select

from radar_online.models import ApiKey, User, UserStatus
from radar_online.tokens import generate_secret, hash_secret

_SLUG_PATTERN = re.compile(r"[a-z0-9-]{1,64}")
_MAX_EMAIL_LENGTH = 254
_MAX_DISPLAY_NAME_LENGTH = 100
_KEY_PREFIX_LENGTH = 8


class AccountCreationError(ValueError):
    """Raised when an account cannot be created from the given details."""


def create_active_account(session: Session, *, email: str, display_name: str, slug: str) -> str:
    """Create an ACTIVE user and their first API key, returning the key in clear.

    The key is returned once and only its hash is stored: the caller must show it
    to its owner and never log it.

    Raises:
        AccountCreationError: invalid details, or the email or slug is already taken.
    """
    email = email.strip().lower()
    display_name = display_name.strip()
    _validate(email, display_name, slug)
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise AccountCreationError(f"An account already uses the email {email!r}")
    if session.exec(select(User).where(User.slug == slug)).first() is not None:
        raise AccountCreationError(f"An account already uses the slug {slug!r}")

    user = User(
        email=email,
        display_name=display_name,
        slug=slug,
        status=UserStatus.ACTIVE,
        approved_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    key = generate_secret()
    session.add(
        ApiKey(
            user_id=persisted_id(user),
            prefix=key[:_KEY_PREFIX_LENGTH],
            key_hash=hash_secret(key),
        )
    )
    session.commit()
    return key


def _validate(email: str, display_name: str, slug: str) -> None:
    if "@" not in email or len(email) > _MAX_EMAIL_LENGTH:
        raise AccountCreationError(f"Invalid email {email!r}")
    if (
        not display_name
        or len(display_name) > _MAX_DISPLAY_NAME_LENGTH
        or not display_name.isprintable()
        or "<" in display_name
        or ">" in display_name
    ):
        raise AccountCreationError(
            "Invalid display name: 1 to 100 printable characters, no '<' or '>'"
        )
    if not _SLUG_PATTERN.fullmatch(slug):
        raise AccountCreationError(
            f"Invalid slug {slug!r}: 1 to 64 lowercase letters, digits or hyphens"
        )
