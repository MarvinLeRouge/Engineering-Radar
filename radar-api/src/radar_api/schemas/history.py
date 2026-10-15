from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategoryScorePoint(BaseModel):
    id: int
    name: str
    value: float | None


class ScoreHistoryPoint(BaseModel):
    scoring_run_id: int
    audit_id: int
    commit_sha: str
    scored_at: datetime
    global_score: float | None
    categories: list[CategoryScorePoint]
