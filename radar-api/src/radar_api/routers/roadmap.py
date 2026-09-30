from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from radar_core.enums import RoadmapStatus
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select

from radar_api.auth import require_api_key
from radar_api.dependencies import get_db_session
from radar_api.schemas.roadmap import EvidenceCandidate, RoadmapItemRead, RoadmapItemStatusUpdate

router = APIRouter(tags=["roadmap"])


def _to_roadmap_item_read(
    roadmap_item: RoadmapItem, improvement_task: ImprovementTask
) -> RoadmapItemRead:
    assert roadmap_item.id is not None
    return RoadmapItemRead(
        id=roadmap_item.id,
        improvement_task_id=roadmap_item.improvement_task_id,
        title=improvement_task.title,
        description=improvement_task.description,
        status=roadmap_item.status.value,
        priority=roadmap_item.priority,
        estimated_effort=roadmap_item.estimated_effort,
        estimated_impact=roadmap_item.estimated_impact,
        promoted_at=roadmap_item.promoted_at,
        done_at=roadmap_item.done_at,
    )


def _linked_finding_ids(session: Session, improvement_task_id: int) -> set[int]:
    return set(
        session.exec(
            select(FindingImprovementTaskLink.finding_id).where(
                FindingImprovementTaskLink.improvement_task_id == improvement_task_id
            )
        ).all()
    )


@router.get("/repositories/{repository_id}/roadmap", response_model=list[RoadmapItemRead])
def list_roadmap_items(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[RoadmapItemRead]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    rows = session.exec(
        select(RoadmapItem, ImprovementTask)
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
    return [_to_roadmap_item_read(item, task) for item, task in rows]


@router.get(
    "/roadmap-items/{roadmap_item_id}/evidence-candidates",
    response_model=list[EvidenceCandidate],
)
def list_roadmap_item_evidence_candidates(
    roadmap_item_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[EvidenceCandidate]:
    roadmap_item = session.get(RoadmapItem, roadmap_item_id)
    if roadmap_item is None:
        raise HTTPException(status_code=404, detail="roadmap item not found")

    linked_finding_ids = _linked_finding_ids(session, roadmap_item.improvement_task_id)
    if not linked_finding_ids:
        return []

    evidence_rows = session.exec(
        select(Evidence).where(Evidence.finding_id.in_(linked_finding_ids))  # type: ignore[attr-defined]
    ).all()
    return [
        EvidenceCandidate(
            id=e.id,  # type: ignore[arg-type]
            finding_id=e.finding_id,  # type: ignore[arg-type]
            evidence_type=e.evidence_type.value,
            content=e.content,
            created_at=e.created_at,
        )
        for e in evidence_rows
    ]


@router.patch(
    "/roadmap-items/{roadmap_item_id}/status",
    response_model=RoadmapItemRead,
    dependencies=[Depends(require_api_key)],
)
def update_roadmap_item_status(
    roadmap_item_id: int,
    payload: RoadmapItemStatusUpdate,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> RoadmapItemRead:
    roadmap_item = session.get(RoadmapItem, roadmap_item_id)
    if roadmap_item is None:
        raise HTTPException(status_code=404, detail="roadmap item not found")
    if roadmap_item.status == payload.status:
        raise HTTPException(
            status_code=400,
            detail=f"roadmap item already has status {payload.status.value}",
        )

    if payload.status == RoadmapStatus.DONE:
        evidence = session.get(Evidence, payload.done_evidence_id)
        if evidence is None:
            raise HTTPException(
                status_code=400,
                detail="done_evidence_id does not reference an existing evidence row",
            )
        linked_finding_ids = _linked_finding_ids(session, roadmap_item.improvement_task_id)
        if evidence.finding_id not in linked_finding_ids:
            raise HTTPException(
                status_code=400,
                detail="done_evidence_id does not belong to a finding linked to this roadmap item",
            )
        roadmap_item.done_evidence_id = payload.done_evidence_id
        roadmap_item.done_at = datetime.now(UTC)
    else:
        roadmap_item.done_evidence_id = None
        roadmap_item.done_at = None

    roadmap_item.status = payload.status
    session.add(roadmap_item)
    session.commit()
    session.refresh(roadmap_item)
    improvement_task = session.get(ImprovementTask, roadmap_item.improvement_task_id)
    assert improvement_task is not None
    return _to_roadmap_item_read(roadmap_item, improvement_task)
