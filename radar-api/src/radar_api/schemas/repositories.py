from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RepositoryRead(BaseModel):
    id: int
    name: str
    path: str
    global_score: float | None
    audit_status: Literal["scored", "not_yet_audited"]
