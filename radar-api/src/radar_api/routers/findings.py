from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from radar_core.enums import FindingSeverity, FindingStatus
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_api.auth import require_api_key
from radar_api.dependencies import get_db_session
from radar_api.schemas.findings import FindingRead, FindingStatusUpdate, FindingVerdictUpdate

router = APIRouter(tags=["findings"])


def _to_finding_read(finding: Finding) -> FindingRead:
    assert finding.id is not None
    return FindingRead(
        id=finding.id,
        criterion_id=finding.criterion_id,
        severity=finding.severity.value,
        description=finding.description,
        file=finding.file,
        line=finding.line,
        status=finding.status.value,
        human_verdict=finding.human_verdict.value,
        detected_at=finding.detected_at,
    )


@router.get("/repositories/{repository_id}/findings", response_model=list[FindingRead])
def list_findings(
    repository_id: int,
    status_filter: FindingStatus | None = Query(  # noqa: B008
        default=None, alias="status"
    ),
    severity: FindingSeverity | None = Query(default=None),  # noqa: B008
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[FindingRead]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    latest_scoring_run = session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()
    if latest_scoring_run is None:
        return []

    query = select(Finding).where(Finding.scoring_run_id == latest_scoring_run.id)
    if status_filter is not None:
        query = query.where(Finding.status == status_filter)
    if severity is not None:
        query = query.where(Finding.severity == severity)

    findings = session.exec(query).all()
    return [_to_finding_read(f) for f in findings]


@router.patch(
    "/findings/{finding_id}/verdict",
    response_model=FindingRead,
    dependencies=[Depends(require_api_key)],
)
def update_finding_verdict(
    finding_id: int,
    payload: FindingVerdictUpdate,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> FindingRead:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    if finding.human_verdict == payload.human_verdict:
        raise HTTPException(
            status_code=400,
            detail=f"finding already has human_verdict {payload.human_verdict.value}",
        )
    finding.human_verdict = payload.human_verdict
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return _to_finding_read(finding)


@router.patch(
    "/findings/{finding_id}/status",
    response_model=FindingRead,
    dependencies=[Depends(require_api_key)],
)
def update_finding_status(
    finding_id: int,
    payload: FindingStatusUpdate,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> FindingRead:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    if finding.status == payload.status:
        raise HTTPException(
            status_code=400,
            detail=f"finding already has status {payload.status.value}",
        )
    finding.status = payload.status
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return _to_finding_read(finding)
