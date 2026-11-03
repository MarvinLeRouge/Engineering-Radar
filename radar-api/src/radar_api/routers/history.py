"""Endpoint returning the score history of a repository across its scoring runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.enums import (
    SEVERITY_RISK_WEIGHT,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    ScoreLevel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.methodology import Category
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import asc, func
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.history import CategoryScorePoint, ScoreHistoryPoint, SeverityRiskPoint

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


_RISK_SEVERITIES = [s for s in FindingSeverity if SEVERITY_RISK_WEIGHT[s] > 0]


def _risk(session: Session, scoring_run: ScoringRun) -> list[SeverityRiskPoint]:
    rows = session.exec(
        select(Finding.severity, Finding.status, Finding.human_verdict, func.count())
        .where(Finding.scoring_run_id == scoring_run.id)
        .group_by(Finding.severity, Finding.status, Finding.human_verdict)
    ).all()
    counted: dict[FindingSeverity, int] = {}
    excluded: dict[FindingSeverity, int] = {}
    for severity, status, verdict, total in rows:
        is_counted = status == FindingStatus.OPEN and verdict != HumanVerdict.FALSE_POSITIVE
        target = counted if is_counted else excluded
        key = FindingSeverity(severity)
        target[key] = target.get(key, 0) + total

    return [
        SeverityRiskPoint(
            severity=severity.value,
            weight=SEVERITY_RISK_WEIGHT[severity],
            count=counted.get(severity, 0),
            excluded=excluded.get(severity, 0),
            weighted=counted.get(severity, 0) * SEVERITY_RISK_WEIGHT[severity],
        )
        for severity in _RISK_SEVERITIES
    ]


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
        .order_by(asc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).all()

    points = []
    for scoring_run, audit in rows:
        risk = _risk(session, scoring_run)
        points.append(
            ScoreHistoryPoint(
                scoring_run_id=scoring_run.id,  # type: ignore[arg-type]
                audit_id=audit.id,  # type: ignore[arg-type]
                commit_sha=audit.commit_sha,
                scored_at=scoring_run.scored_at,
                global_score=scoring_run.global_score,
                categories=_category_scores(session, scoring_run),
                risk=risk,
                risk_index=sum(entry.weighted for entry in risk),
            )
        )
    return points
