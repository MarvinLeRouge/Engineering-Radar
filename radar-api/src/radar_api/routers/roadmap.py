from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.roadmap import RoadmapItemRead

router = APIRouter(tags=["roadmap"])


def _to_roadmap_item_read(roadmap_item: RoadmapItem) -> RoadmapItemRead:
    assert roadmap_item.id is not None
    return RoadmapItemRead(
        id=roadmap_item.id,
        improvement_task_id=roadmap_item.improvement_task_id,
        status=roadmap_item.status.value,
        priority=roadmap_item.priority,
        estimated_effort=roadmap_item.estimated_effort,
        estimated_impact=roadmap_item.estimated_impact,
        promoted_at=roadmap_item.promoted_at,
        done_at=roadmap_item.done_at,
    )


@router.get("/repositories/{repository_id}/roadmap", response_model=list[RoadmapItemRead])
def list_roadmap_items(
    repository_id: int, session: Session = Depends(get_db_session)  # noqa: B008
) -> list[RoadmapItemRead]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    roadmap_items = session.exec(
        select(RoadmapItem)
        .join(ImprovementTask, ImprovementTask.id == RoadmapItem.improvement_task_id)  # type: ignore[arg-type]
        .join(
            FindingImprovementTaskLink,
            FindingImprovementTaskLink.improvement_task_id == ImprovementTask.id,  # type: ignore[arg-type]
        )
        .join(Finding, Finding.id == FindingImprovementTaskLink.finding_id)  # type: ignore[arg-type]
        .join(ScoringRun, ScoringRun.id == Finding.scoring_run_id)  # type: ignore[arg-type]
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .distinct()
    ).all()
    return [_to_roadmap_item_read(item) for item in roadmap_items]
