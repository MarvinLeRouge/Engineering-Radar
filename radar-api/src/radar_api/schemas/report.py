"""Pydantic schemas for the scored repository report response."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FindingReport(BaseModel):
    """One finding listed under a criterion of the repository report."""

    id: int
    severity: str
    description: str
    file: str | None
    line: int | None
    status: str
    human_verdict: str
    recommendation: str | None


class CriterionReport(BaseModel):
    """One criterion of the repository report with its score status and findings."""

    id: int
    name: str
    status: Literal["scored", "not_applicable", "not_yet_audited"]
    value: float | None
    na_reason: str | None
    findings: list[FindingReport]


class CategoryReport(BaseModel):
    """One category of the repository report with its score and criteria."""

    id: int
    name: str
    order: int
    status: Literal["scored", "not_yet_audited"]
    value: float | None
    confidence: str | None
    criteria: list[CriterionReport]


class RepositoryReport(BaseModel):
    """Full scored report of a repository for one scoring run."""

    repository_id: int
    repository_name: str
    commit_sha: str
    audited_at: datetime
    scored_at: datetime
    categories: list[CategoryReport]
