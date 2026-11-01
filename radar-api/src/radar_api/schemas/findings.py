"""Pydantic schemas for finding responses and finding update requests."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from radar_core.enums import FindingStatus, HumanVerdict


class FindingRead(BaseModel):
    """Public representation of a finding returned by the findings endpoints."""

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
    """Request body for setting the human verdict of a finding."""

    human_verdict: HumanVerdict


class FindingStatusUpdate(BaseModel):
    """Request body for setting the status of a finding."""

    status: FindingStatus
