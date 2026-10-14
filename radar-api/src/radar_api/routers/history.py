from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun
from sqlalchemy import asc
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.history import ScoreHistoryPoint

router = APIRouter(tags=["history"])


@router.get("/repositories/{repository_id}/score-history", response_model=list[ScoreHistoryPoint])
def get_score_history(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[ScoreHistoryPoint]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    rows = session.exec(
        select(ScoringRun, Audit)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(asc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).all()

    return [
        ScoreHistoryPoint(
            scoring_run_id=scoring_run.id,  # type: ignore[arg-type]
            audit_id=audit.id,  # type: ignore[arg-type]
            commit_sha=audit.commit_sha,
            scored_at=scoring_run.scored_at,
            global_score=scoring_run.global_score,
        )
        for scoring_run, audit in rows
    ]
