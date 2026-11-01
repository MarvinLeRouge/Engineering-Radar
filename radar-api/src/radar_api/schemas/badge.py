"""Pydantic schema for the repository quality badge response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BadgeResponse(BaseModel):
    """Shields.io endpoint payload for the repository quality badge."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = Field(default=1, alias="schemaVersion")
    label: str
    message: str
    color: str
