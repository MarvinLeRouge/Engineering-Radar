"""Publication payload contract (v1) shared by radar-api (builds it) and radar-online.

Holds only what ADR 0014 allows out of the local machine: the global and category
scores of one scoring run. Every model forbids unknown fields, so a newer local
version can never leak a field an older server would silently store; free text is
limited to short, printable labels, so no field can carry markup or a data dump.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from radar_core.enums import Confidence

# Printable text without markup: no control characters (incl. newlines), no < or >.
_LABEL = r"^[^\x00-\x1f\x7f<>]+$"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class PublishedRepositoryRef(_Contract):
    """The repository a report is published under, scoped to its owner."""

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    display_name: str = Field(min_length=1, max_length=100, pattern=_LABEL)


class PublishedCategory(_Contract):
    """One category score; never any criterion, finding or severity count."""

    name: str = Field(min_length=1, max_length=100, pattern=_LABEL)
    order: int = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=100)
    status: Literal["scored", "not_yet_audited"]
    implemented: bool
    value: float | None = Field(default=None, ge=0, le=10)
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def _value_only_when_scored(self) -> Self:
        if self.value is not None and (self.status != "scored" or not self.implemented):
            raise ValueError("only a scored, implemented category carries a value")
        return self


class PublicationPayload(_Contract):
    """Sanitized report of one scoring run, as sent to radar-online."""

    schema_version: Literal[1]
    repository: PublishedRepositoryRef
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    scored_at: AwareDatetime
    methodology_version: str = Field(min_length=1, max_length=50, pattern=_LABEL)
    global_score: float | None = Field(default=None, ge=0, le=10)
    categories: list[PublishedCategory] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _consistent_categories(self) -> Self:
        names = [category.name for category in self.categories]
        orders = [category.order for category in self.categories]
        if len(set(names)) != len(names) or len(set(orders)) != len(orders):
            raise ValueError("category names and orders must be unique")
        if self.global_score is not None and all(c.value is None for c in self.categories):
            raise ValueError("a global score needs at least one scored category")
        return self
