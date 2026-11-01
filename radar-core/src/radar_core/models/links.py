"""Association table linking findings to the improvement tasks that address them."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class FindingImprovementTaskLink(SQLModel, table=True):
    """Join row recording that an improvement task addresses a given finding."""

    __tablename__ = "finding_improvement_task_link"

    finding_id: int = Field(foreign_key="finding.id", primary_key=True)
    improvement_task_id: int = Field(foreign_key="improvement_task.id", primary_key=True)
