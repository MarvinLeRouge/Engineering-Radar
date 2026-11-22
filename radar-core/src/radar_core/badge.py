"""Shields.io quality badge shared by radar-api (local) and radar-online (public)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

BADGE_LABEL = "quality"


class BadgeResponse(BaseModel):
    """Shields.io endpoint payload for the repository quality badge."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = Field(default=1, alias="schemaVersion")
    label: str
    message: str
    color: str


def badge_color(score: float) -> str:
    """Return the shields.io color of a 0 to 10 score, the same bands as the dashboard gauges."""
    if score >= 8:
        return "brightgreen"
    if score >= 6:
        return "green"
    if score >= 4:
        return "yellow"
    if score >= 2:
        return "orange"
    return "red"
