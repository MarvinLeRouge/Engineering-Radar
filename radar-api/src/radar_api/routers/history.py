"""Endpoint returning the score history of a repository across its scoring runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import asc
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.history import CategoryScorePoint, ScoreHistoryPoint

router = APIRouter(tags=["history"])


def _category_scores(session: Session, scoring_run: ScoringRun) -> list[CategoryScorePoint]:
    # Mirrors get_repository_report's own defensive level filter in
    # repositories.py, rather than relying solely on the convention that
    # category_id is only ever set on CATEGORY-level rows.
    rows = session.exec(
        select(Category, Score)
        .join(
            Score,
            (Score.category_id == Category.id)  # type: ignore[arg-type]
            & (Score.scoring_run_id == scoring_run.id)
            & (Score.level == ScoreLevel.CATEGORY),
            isouter=True,
        )
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(Category.order)  # type: ignore[arg-type]
    ).all()

    return [
        CategoryScorePoint(id=category.id, name=category.name, value=score.value if score else None)  # type: ignore[arg-type]
        for category, score in rows
    ]


@router.get("/repositories/{repository_id}/score-history", response_model=list[ScoreHistoryPoint])
def get_score_history(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[ScoreHistoryPoint]:
    """Return one score history point per scoring run of a repository, oldest first."""
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
            categories=_category_scores(session, scoring_run),
        )
        for scoring_run, audit in rows
    ]
