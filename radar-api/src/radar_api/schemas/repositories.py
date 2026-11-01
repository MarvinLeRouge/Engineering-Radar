"""Pydantic schemas for repository list and detail responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RepositoryRead(BaseModel):
    """Repository summary with its latest global score and audit status."""

    id: int
    name: str
    path: str
    global_score: float | None
    audit_status: Literal["scored", "not_yet_audited"]
