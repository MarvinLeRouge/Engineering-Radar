from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.enums import ScoreLevel
from radar_core.finding_ordering import sort_findings_by_priority
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.badge import BadgeResponse
from radar_api.schemas.report import (
    CategoryReport,
    CriterionReport,
    FindingReport,
    RepositoryReport,
)
from radar_api.schemas.repositories import RepositoryRead

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _latest_scoring_run(session: Session, repository_id: int) -> ScoringRun | None:
    return session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()


_BADGE_LABEL = "quality"


def _badge_color(score: float) -> str:
    if score >= 8:
        return "brightgreen"
    if score >= 6:
        return "green"
    if score >= 4:
        return "yellow"
    if score >= 2:
        return "orange"
    return "red"


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


@router.get("/{repository_id}/report", response_model=RepositoryReport)
def get_repository_report(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> RepositoryReport:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    scoring_run = _latest_scoring_run(session, repository_id)
    if scoring_run is None:
        raise HTTPException(status_code=404, detail="no score found for this repository")

    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None

    categories = session.exec(
        select(Category)
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(Category.order)  # type: ignore[arg-type]
    ).all()

    scores = session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    category_scores = {s.category_id: s for s in scores if s.level == ScoreLevel.CATEGORY}
    criterion_scores = {s.criterion_id: s for s in scores if s.level == ScoreLevel.CRITERION}

    findings = session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    findings_by_criterion: dict[int | None, list[Finding]] = {}
    for finding in sort_findings_by_priority(findings):
        findings_by_criterion.setdefault(finding.criterion_id, []).append(finding)

    finding_ids = [f.id for f in findings if f.id is not None]
    recommendations = session.exec(
        select(Recommendation).where(
            Recommendation.finding_id.in_(finding_ids)  # type: ignore[attr-defined]
        )
    ).all()
    recommendation_by_finding = {r.finding_id: r.text for r in recommendations}

    category_reports = []
    for category in categories:
        category_score = category_scores.get(category.id)
        criteria = session.exec(
            select(Criterion).where(Criterion.category_id == category.id).order_by(Criterion.id)  # type: ignore[arg-type]
        ).all()
        criterion_reports = []
        for criterion in criteria:
            criterion_score = criterion_scores.get(criterion.id)
            if criterion_score is None:
                criterion_status = "not_yet_audited"
            elif criterion_score.na_reason is not None:
                criterion_status = "not_applicable"
            else:
                criterion_status = "scored"

            finding_reports = [
                FindingReport(
                    id=f.id,  # type: ignore[arg-type]
                    severity=f.severity.value,
                    description=f.description,
                    file=f.file,
                    line=f.line,
                    status=f.status.value,
                    human_verdict=f.human_verdict.value,
                    recommendation=recommendation_by_finding.get(f.id),  # type: ignore[arg-type]
                )
                for f in findings_by_criterion.get(criterion.id, [])
            ]
            criterion_reports.append(
                CriterionReport(
                    id=criterion.id,  # type: ignore[arg-type]
                    name=criterion.name,
                    status=criterion_status,  # type: ignore[arg-type]
                    value=(
                        criterion_score.value
                        if criterion_score is not None and criterion_status != "not_applicable"
                        else None
                    ),
                    na_reason=criterion_score.na_reason if criterion_score else None,
                    findings=finding_reports,
                )
            )
        category_reports.append(
            CategoryReport(
                id=category.id,  # type: ignore[arg-type]
                name=category.name,
                order=category.order,
                status="scored" if category_score is not None else "not_yet_audited",
                value=category_score.value if category_score else None,
                confidence=category_score.confidence.value if category_score else None,
                criteria=criterion_reports,
            )
        )

    return RepositoryReport(
        repository_id=repository.id,  # type: ignore[arg-type]
        repository_name=repository.name,
        commit_sha=audit.commit_sha,
        audited_at=audit.audited_at,
        scored_at=scoring_run.scored_at,
        categories=category_reports,
    )


@router.get("/{repository_id}/badge", response_model=BadgeResponse)
def get_repository_badge(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> BadgeResponse:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    scoring_run = _latest_scoring_run(session, repository_id)
    if scoring_run is None or scoring_run.global_score is None:
        return BadgeResponse(label=_BADGE_LABEL, message="not yet audited", color="lightgrey")

    return BadgeResponse(
        label=_BADGE_LABEL,
        message=f"{scoring_run.global_score:.1f}/10",
        color=_badge_color(scoring_run.global_score),
    )
