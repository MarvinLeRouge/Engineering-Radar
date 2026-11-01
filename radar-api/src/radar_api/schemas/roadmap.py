"""Pydantic schemas for roadmap item and evidence candidate responses and status updates."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator
from radar_core.enums import RoadmapStatus


class RoadmapItemRead(BaseModel):
    """Roadmap item as returned by the roadmap endpoints."""

    id: int
    improvement_task_id: int
    title: str
    description: str
    category_name: str
    criterion_name: str
    status: str
    priority: float
    estimated_effort: str | None
    estimated_impact: str | None
    promoted_at: datetime
    done_at: datetime | None


class RoadmapItemStatusUpdate(BaseModel):
    """Request body for changing a roadmap item status, with optional done evidence."""

    status: RoadmapStatus
    done_evidence_id: int | None = None

    @model_validator(mode="after")
    def _require_evidence_for_done(self) -> RoadmapItemStatusUpdate:
        if self.status == RoadmapStatus.DONE and self.done_evidence_id is None:
            raise ValueError("done_evidence_id is required when status is DONE")
        return self


class EvidenceCandidate(BaseModel):
    """Evidence row that can serve as done evidence for a roadmap item."""

    id: int
    finding_id: int
    evidence_type: str
    content: str
    created_at: datetime
