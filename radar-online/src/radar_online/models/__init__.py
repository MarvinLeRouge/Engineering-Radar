"""radar-online tables, registered on SQLModel.metadata when imported.

Never import radar_core.models here or in Alembic: radar-online must not host the local
audit data (ADR 0014). Deleting a user cascades in the database to their keys, tokens,
repositories and reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from radar_core.types import UTCDateTime
from sqlalchemy import JSON, Column, Dialect, ForeignKey, String, TypeDecorator, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


def _created_at() -> Any:
    return Field(default_factory=_now, sa_column=Column(UTCDateTime(), nullable=False))


def _optional_datetime() -> Any:
    return Field(default=None, sa_column=Column(UTCDateTime(), nullable=True))


def _owner(table: str) -> Any:
    return Field(
        sa_column=Column(ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=False, index=True)
    )


class LowercaseString(TypeDecorator[str]):
    """A string stored, and compared in queries, lowercase and trimmed (email addresses)."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return value.strip().lower() if value is not None else None


class UserStatus(StrEnum):
    """Where a registration stands, from the request to an active account."""

    PENDING_EMAIL = "PENDING_EMAIL"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class ActionTokenPurpose(StrEnum):
    """What a single-use email link lets its holder do."""

    CONFIRM_EMAIL = "CONFIRM_EMAIL"
    REVIEW_REQUEST = "REVIEW_REQUEST"
    REVEAL_KEY = "REVEAL_KEY"
    REGENERATE_KEY = "REGENERATE_KEY"


class User(SQLModel, table=True):
    """A person who requested, or holds, a radar-online account."""

    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    # Lowercase so uniqueness and lookups never depend on how the address was typed.
    email: str = Field(sa_column=Column(LowercaseString(254), unique=True, nullable=False))
    display_name: str = Field(max_length=100)
    slug: str = Field(unique=True, max_length=64)
    message: str | None = Field(default=None, max_length=1000)
    status: UserStatus = Field(
        default=UserStatus.PENDING_EMAIL,
        sa_column=Column(
            SAEnum(
                UserStatus,
                create_constraint=True,
                validate_strings=True,
                name="ck_user_status_valid",
            ),
            nullable=False,
        ),
    )
    created_at: datetime = _created_at()
    approved_at: datetime | None = _optional_datetime()


class ApiKey(SQLModel, table=True):
    """A user's API key, stored as a hash; `prefix` identifies it in logs and lists."""

    __tablename__ = "api_key"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner("user")
    prefix: str = Field(max_length=8)
    key_hash: str = Field(unique=True, max_length=64)
    created_at: datetime = _created_at()
    revoked_at: datetime | None = _optional_datetime()


class ActionToken(SQLModel, table=True):
    """A single-use, expiring secret sent by email, stored as a hash."""

    __tablename__ = "action_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner("user")
    purpose: ActionTokenPurpose = Field(
        sa_column=Column(
            SAEnum(
                ActionTokenPurpose,
                create_constraint=True,
                validate_strings=True,
                name="ck_action_token_purpose_valid",
            ),
            nullable=False,
        )
    )
    token_hash: str = Field(unique=True, max_length=64)
    created_at: datetime = _created_at()
    expires_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    used_at: datetime | None = _optional_datetime()


class PublishedRepository(SQLModel, table=True):
    """A repository a user publishes reports for, under their own namespace."""

    __tablename__ = "published_repository"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_published_repository_slug"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner("user")
    slug: str = Field(max_length=64)
    display_name: str = Field(max_length=100)
    created_at: datetime = _created_at()


class PublishedReport(SQLModel, table=True):
    """The published scores of one commit; a new upload for that commit replaces it."""

    __tablename__ = "published_report"
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", name="uq_published_report_commit"),
    )

    id: int | None = Field(default=None, primary_key=True)
    repository_id: int = _owner("published_repository")
    commit_sha: str = Field(max_length=40)
    scored_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    uploaded_at: datetime = _created_at()
    methodology_version: str = Field(max_length=20)
    schema_version: int
    global_score: float | None = None
    # The validated radar_core.publication.PublicationPayload, as JSON.
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
