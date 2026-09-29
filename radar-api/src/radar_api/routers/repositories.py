from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.repositories import RepositoryRead

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _latest_scoring_run(session: Session, repository_id: int) -> ScoringRun | None:
    return session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()


def _to_repository_read(session: Session, repository: Repository) -> RepositoryRead:
    assert repository.id is not None
    scoring_run = _latest_scoring_run(session, repository.id)
    return RepositoryRead(
        id=repository.id,
        name=repository.name,
        path=repository.path,
        global_score=scoring_run.global_score if scoring_run else None,
        audit_status="scored" if scoring_run is not None else "not_yet_audited",
    )


@router.get("", response_model=list[RepositoryRead])
def list_repositories(
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[RepositoryRead]:
    repositories = session.exec(select(Repository)).all()
    return [_to_repository_read(session, repo) for repo in repositories]


@router.get("/{repository_id}", response_model=RepositoryRead)
def get_repository(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> RepositoryRead:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return _to_repository_read(session, repository)
