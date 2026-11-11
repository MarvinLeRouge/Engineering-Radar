"""Endpoint returning the score history of a repository across its scoring runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session, col, select

from radar_api.dependencies import get_db_session
from radar_api.risk import compute_risk
from radar_api.schemas.history import CategoryScorePoint, ScoreHistoryPoint

router = APIRouter(tags=["history"])


def _category_scores(
    session: Session, scoring_run: ScoringRun, implemented: set[int]
) -> list[CategoryScorePoint]:
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

    points = [
        CategoryScorePoint(
            id=category.id,  # type: ignore[arg-type]
            name=category.name,
            value=score.value if score else None,
            implemented=category.id in implemented,
        )
        for category, score in rows
    ]
    # Categories radar-audit cannot score yet go last, keeping the taxonomy order otherwise.
    return sorted(points, key=lambda point: not point.implemented)


def _implemented_category_ids(session: Session, methodology_version_id: int) -> set[int]:
    """Categories of a methodology version with at least one implemented criterion."""
    return set(
        session.exec(
            select(Criterion.category_id)
            .join(Category, Category.id == Criterion.category_id)  # type: ignore[arg-type]
            .where(
                Category.methodology_version_id == methodology_version_id,
                Criterion.implemented,
            )
        ).all()
    )


@router.get("/repositories/{repository_id}/score-history", response_model=list[ScoreHistoryPoint])
def get_score_history(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[ScoreHistoryPoint]:
    """Return one score history point per scoring run, oldest first, with its weighted risk."""
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    rows = session.exec(
        select(ScoringRun, Audit)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(col(ScoringRun.scored_at).asc())
    ).all()

    # One query per methodology version, not per run: a history rarely spans more than one.
    implemented_by_version = {
        version_id: _implemented_category_ids(session, version_id)
        for version_id in {scoring_run.methodology_version_id for scoring_run, _ in rows}
    }
    points = []
    for scoring_run, audit in rows:
        risk = compute_risk(session, scoring_run)
        points.append(
            ScoreHistoryPoint(
                scoring_run_id=scoring_run.id,  # type: ignore[arg-type]
                audit_id=audit.id,  # type: ignore[arg-type]
                commit_sha=audit.commit_sha,
                scored_at=scoring_run.scored_at,
                global_score=scoring_run.global_score,
                categories=_category_scores(
                    session, scoring_run, implemented_by_version[scoring_run.methodology_version_id]
                ),
                risk=risk,
                risk_index=sum(entry.weighted for entry in risk),
            )
        )
    return points
