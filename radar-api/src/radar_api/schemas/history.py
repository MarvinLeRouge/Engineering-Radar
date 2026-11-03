"""Pydantic schemas for the repository score history response."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategoryScorePoint(BaseModel):
    """Score of one category at a scoring run, or None when it was not scored."""

    id: int
    name: str
    value: float | None


class SeverityRiskPoint(BaseModel):
    """Findings of one severity at a scoring run and their weighted risk.

    `count` covers OPEN findings not marked FALSE_POSITIVE and `excluded` the rest;
    `wont_fix` is the part of `excluded` accepted as WONT_FIX true positives (still in the score);
    `weighted` is `count` times the severity's risk `weight`.
    """

    severity: str
    weight: int
    count: int
    excluded: int
    wont_fix: int
    weighted: int


class ScoreHistoryPoint(BaseModel):
    """One scoring run of a repository: global and per-category scores, and weighted risk."""

    scoring_run_id: int
    audit_id: int
    commit_sha: str
    scored_at: datetime
    global_score: float | None
    categories: list[CategoryScorePoint]
    risk: list[SeverityRiskPoint]
    risk_index: int
