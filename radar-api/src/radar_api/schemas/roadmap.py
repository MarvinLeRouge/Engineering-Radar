from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator
from radar_core.enums import RoadmapStatus


class RoadmapItemRead(BaseModel):
    id: int
    improvement_task_id: int
    status: str
    priority: int
    estimated_effort: str | None
    estimated_impact: str | None
    promoted_at: datetime
    done_at: datetime | None


class RoadmapItemStatusUpdate(BaseModel):
    status: RoadmapStatus
    done_evidence_id: int | None = None

    @model_validator(mode="after")
    def _require_evidence_for_done(self) -> RoadmapItemStatusUpdate:
        if self.status == RoadmapStatus.DONE and self.done_evidence_id is None:
            raise ValueError("done_evidence_id is required when status is DONE")
        return self
