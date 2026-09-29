from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FindingReport(BaseModel):
    id: int
    severity: str
    description: str
    file: str | None
    line: int | None
    status: str
    human_verdict: str
    recommendation: str | None


class CriterionReport(BaseModel):
    id: int
    name: str
    status: Literal["scored", "not_applicable", "not_yet_audited"]
    value: float | None
    na_reason: str | None
    findings: list[FindingReport]


class CategoryReport(BaseModel):
    id: int
    name: str
    order: int
    status: Literal["scored", "not_yet_audited"]
    value: float | None
    confidence: str | None
    criteria: list[CriterionReport]


class RepositoryReport(BaseModel):
    repository_id: int
    repository_name: str
    commit_sha: str
    audited_at: datetime
    scored_at: datetime
    categories: list[CategoryReport]
