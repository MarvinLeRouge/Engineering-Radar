"""Pydantic schemas for finding responses and finding update requests."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints
from radar_core.enums import FindingStatus, HumanVerdict
from radar_core.models.finding import VERDICT_NOTE_MAX_LENGTH


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
    verdict_note: str | None
    detected_at: datetime


class FindingVerdictUpdate(BaseModel):
    """Request body for setting the human verdict of a finding."""

    human_verdict: HumanVerdict


class FindingStatusUpdate(BaseModel):
    """Request body for setting the status of a finding."""

    status: FindingStatus


class FindingNoteUpdate(BaseModel):
    """Request body for setting the explanatory note of a finding; blank text clears it."""

    # Trimmed before the length check, so surrounding spaces never cause a rejection.
    verdict_note: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=VERDICT_NOTE_MAX_LENGTH)
    ]
