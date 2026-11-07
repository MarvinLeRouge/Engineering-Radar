"""Random secrets for API keys and action tokens, and how they are stored."""

from __future__ import annotations

import hashlib
import secrets

# 32 random bytes: high entropy, so a fast SHA-256 is enough to store them (no slow KDF).
_SECRET_BYTES = 32


def generate_secret() -> str:
    """Return a new URL-safe random secret, shown to its owner once and never stored."""
    return secrets.token_urlsafe(_SECRET_BYTES)


def hash_secret(secret: str) -> str:
    """Return the hex SHA-256 of `secret`, the only form kept in the database."""
    return hashlib.sha256(secret.encode()).hexdigest()
