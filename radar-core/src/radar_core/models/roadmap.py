from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import RoadmapStatus
from radar_core.types import UTCDateTime


class ImprovementTask(SQLModel, table=True):
    __tablename__ = "improvement_task"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    criterion_id: int = Field(foreign_key="criterion.id", index=True)
    # The grouping key's file component -- None for a repo-wide finding with no
    # file (e.g. a dependency CVE), or for a criterion whose findings bypass
    # file-based grouping entirely (dependency circularity, code duplication).
    file: str | None = Field(default=None, index=True)
    # Stable identity for "the same underlying task" across re-scoring runs --
    # either a hash of (criterion_id, file), or a Finding.fingerprint reused
    # verbatim for an atomic (bypass) task. Used to upsert instead of
    # delete-and-recreate, so a human-set RoadmapItem survives a re-audit.
    group_key: str = Field(unique=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )


class RoadmapItem(SQLModel, table=True):
    __tablename__ = "roadmap_item"

    id: int | None = Field(default=None, primary_key=True)
    improvement_task_id: int = Field(foreign_key="improvement_task.id", unique=True, index=True)
    status: RoadmapStatus = Field(
        default=RoadmapStatus.TODO,
        sa_column=Column(
            SAEnum(
                RoadmapStatus,
                create_constraint=True,
                validate_strings=True,
                name="ck_roadmap_item_status_valid",
            ),
            nullable=False,
        ),
    )
    priority: float
    estimated_effort: str | None = None
    estimated_impact: str | None = None
    promoted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )
    done_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime()))
    done_evidence_id: int | None = Field(default=None, foreign_key="evidence.id")
