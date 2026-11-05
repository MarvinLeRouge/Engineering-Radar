"""Pydantic schemas for the scored repository report response."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from radar_api.schemas.history import SeverityRiskPoint


class FindingReport(BaseModel):
    """One finding listed under a criterion of the repository report."""

    id: int
    severity: str
    description: str
    file: str | None
    line: int | None
    status: str
    human_verdict: str
    verdict_note: str | None
    recommendation: str | None


class CriterionReport(BaseModel):
    """One criterion of the repository report with its score status and findings."""

    id: int
    name: str
    status: Literal["scored", "not_applicable", "not_yet_audited"]
    implemented: bool
    value: float | None
    na_reason: str | None
    # First page only: the rest comes from the criterion findings endpoint.
    findings: list[FindingReport]
    findings_total: int
    # Findings not dismissed as false positives, by severity; absent severities are omitted.
    severity_counts: dict[str, int]
    dismissed_count: int


class CategoryReport(BaseModel):
    """One category of the repository report with its score and criteria."""

    id: int
    name: str
    order: int
    status: Literal["scored", "not_yet_audited"]
    # True when at least one of its criteria is implemented.
    implemented: bool
    value: float | None
    confidence: str | None
    criteria: list[CriterionReport]


class RepositoryReport(BaseModel):
    """Full scored report of a repository for one scoring run."""

    repository_id: int
    repository_name: str
    scoring_run_id: int
    commit_sha: str
    audited_at: datetime
    scored_at: datetime
    categories: list[CategoryReport]
    risk: list[SeverityRiskPoint]
    risk_index: int
