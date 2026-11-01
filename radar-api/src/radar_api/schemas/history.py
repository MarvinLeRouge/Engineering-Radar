"""Pydantic schemas for the repository score history response."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategoryScorePoint(BaseModel):
    """Score of one category at a scoring run, or None when it was not scored."""

    id: int
    name: str
    value: float | None


class ScoreHistoryPoint(BaseModel):
    """One scoring run of a repository with its global and per-category scores."""

    scoring_run_id: int
    audit_id: int
    commit_sha: str
    scored_at: datetime
    global_score: float | None
    categories: list[CategoryScorePoint]
