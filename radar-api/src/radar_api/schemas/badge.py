from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BadgeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = Field(default=1, alias="schemaVersion")
    label: str
    message: str
    color: str
