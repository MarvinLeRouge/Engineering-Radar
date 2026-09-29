from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from radar_core.enums import FindingStatus, HumanVerdict


class FindingRead(BaseModel):
    id: int
    criterion_id: int
    severity: str
    description: str
    file: str | None
    line: int | None
    status: str
    human_verdict: str
    detected_at: datetime


class FindingVerdictUpdate(BaseModel):
    human_verdict: HumanVerdict


class FindingStatusUpdate(BaseModel):
    status: FindingStatus
