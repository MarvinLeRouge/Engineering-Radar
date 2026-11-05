"""Repository endpoints: listing, detail, scored report and README badge."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException, Query
from radar_core.enums import HumanVerdict, ScoreLevel
from radar_core.finding_ordering import PRIORITY_ORDER_BY
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc, func
from sqlmodel import Session, col, select

from radar_api.dependencies import get_db_session
from radar_api.risk import compute_risk
from radar_api.schemas.badge import BadgeResponse
from radar_api.schemas.report import (
    CategoryReport,
    CriterionReport,
    FindingReport,
    RepositoryReport,
)
from radar_api.schemas.repositories import RepositoryRead

router = APIRouter(prefix="/repositories", tags=["repositories"])

# Findings sent per criterion: the report holds the first page, the findings endpoint the rest.
FINDINGS_PAGE_SIZE = 1000


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


def _resolve_scoring_run(
    session: Session, repository_id: int, scoring_run_id: int | None
) -> ScoringRun | None:
    if scoring_run_id is None:
        return _latest_scoring_run(session, repository_id)
    return session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(ScoringRun.id == scoring_run_id, Audit.repository_id == repository_id)
    ).first()


def _build_finding_report(
    finding: Finding, recommendation_by_finding: dict[int, str]
) -> FindingReport:
    return FindingReport(
        id=finding.id,  # type: ignore[arg-type]
        severity=finding.severity.value,
        description=finding.description,
        file=finding.file,
        line=finding.line,
        status=finding.status.value,
        human_verdict=finding.human_verdict.value,
        verdict_note=finding.verdict_note,
        recommendation=recommendation_by_finding.get(finding.id),  # type: ignore[arg-type]
    )


def _criterion_status(criterion_score: Score | None) -> str:
    if criterion_score is None:
        return "not_yet_audited"
    if criterion_score.na_reason is not None:
        return "not_applicable"
    return "scored"


@dataclass
class _FindingCounts:
    severity_counts: dict[str, int] = field(default_factory=dict)
    dismissed_count: int = 0

    @property
    def total(self) -> int:
        return sum(self.severity_counts.values()) + self.dismissed_count


def _finding_counts_by_criterion(
    session: Session, scoring_run_id: int
) -> dict[int, _FindingCounts]:
    rows = session.exec(
        select(Finding.criterion_id, Finding.severity, Finding.human_verdict, func.count())
        .where(Finding.scoring_run_id == scoring_run_id)
        .group_by(col(Finding.criterion_id), col(Finding.severity), col(Finding.human_verdict))
    ).all()
    counts: dict[int, _FindingCounts] = {}
    for criterion_id, severity, human_verdict, count in rows:
        criterion_counts = counts.setdefault(criterion_id, _FindingCounts())
        if human_verdict == HumanVerdict.FALSE_POSITIVE:
            criterion_counts.dismissed_count += count
        else:
            # The enum is a StrEnum: its value is the string key the dashboard reads.
            key = str(severity)
            severity_counts = criterion_counts.severity_counts
            severity_counts[key] = severity_counts.get(key, 0) + count
    return counts


def _findings_page(
    session: Session, scoring_run_id: int, criterion_id: int, offset: int
) -> list[FindingReport]:
    """One page of a criterion's findings, in priority order, with their recommendations."""
    page = (
        select(Finding)
        .where(Finding.scoring_run_id == scoring_run_id, Finding.criterion_id == criterion_id)
        .order_by(*PRIORITY_ORDER_BY)
        .offset(offset)
        .limit(FINDINGS_PAGE_SIZE)
    )
    findings = session.exec(page).all()
    if not findings:
        return []
    # A subquery, not a list of ids: SQLite caps bound parameters per statement.
    page_ids = page.with_only_columns(col(Finding.id))
    recommendations = session.exec(
        select(Recommendation).where(col(Recommendation.finding_id).in_(page_ids))
    ).all()
    recommendation_by_finding = {r.finding_id: r.text for r in recommendations}
    return [_build_finding_report(f, recommendation_by_finding) for f in findings]


def _build_criterion_report(
    session: Session,
    scoring_run_id: int,
    criterion: Criterion,
    criterion_score: Score | None,
    counts: _FindingCounts,
) -> CriterionReport:
    status = _criterion_status(criterion_score)
    return CriterionReport(
        id=criterion.id,  # type: ignore[arg-type]
        name=criterion.name,
        status=status,  # type: ignore[arg-type]
        implemented=criterion.implemented,
        value=criterion_score.value
        if criterion_score is not None and status != "not_applicable"
        else None,
        na_reason=criterion_score.na_reason if criterion_score else None,
        findings=_findings_page(session, scoring_run_id, criterion.id, 0)  # type: ignore[arg-type]
        if counts.total
        else [],
        findings_total=counts.total,
        severity_counts=counts.severity_counts,
        dismissed_count=counts.dismissed_count,
    )


def _build_category_report(
    session: Session,
    category: Category,
    category_score: Score | None,
    scoring_run_id: int,
    criterion_scores: dict[int | None, Score],
    counts_by_criterion: dict[int, _FindingCounts],
) -> CategoryReport:
    criteria = session.exec(
        select(Criterion).where(Criterion.category_id == category.id).order_by(Criterion.id)  # type: ignore[arg-type]
    ).all()
    criterion_reports = [
        _build_criterion_report(
            session,
            scoring_run_id,
            criterion,
            criterion_scores.get(criterion.id),
            counts_by_criterion.get(criterion.id, _FindingCounts()),  # type: ignore[arg-type]
        )
        # Stable sort: implemented criteria first, each group in its own order.
        for criterion in sorted(criteria, key=lambda c: not c.implemented)
    ]
    return CategoryReport(
        id=category.id,  # type: ignore[arg-type]
        name=category.name,
        order=category.order,
        status="scored" if category_score is not None else "not_yet_audited",
        implemented=any(c.implemented for c in criteria),
        value=category_score.value if category_score else None,
        confidence=category_score.confidence.value if category_score else None,
        criteria=criterion_reports,
    )


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
    """Return every registered repository with its latest global score and audit status."""
    repositories = session.exec(select(Repository)).all()
    return [_to_repository_read(session, repo) for repo in repositories]


@router.get("/{repository_id}", response_model=RepositoryRead)
def get_repository(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> RepositoryRead:
    """Return one repository with its latest global score and audit status, or 404 if unknown."""
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return _to_repository_read(session, repository)


@router.get("/{repository_id}/report", response_model=RepositoryReport)
def get_repository_report(
    repository_id: int,
    scoring_run_id: int | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> RepositoryReport:
    """Build the scored report of a repository from the requested or latest scoring run."""
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    scoring_run = _resolve_scoring_run(session, repository_id, scoring_run_id)
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

    counts_by_criterion = _finding_counts_by_criterion(session, scoring_run.id)  # type: ignore[arg-type]

    category_reports = [
        _build_category_report(
            session,
            category,
            category_scores.get(category.id),
            scoring_run.id,  # type: ignore[arg-type]
            criterion_scores,
            counts_by_criterion,
        )
        for category in categories
    ]
    # Categories radar-audit cannot score yet go last, keeping the taxonomy order otherwise.
    category_reports.sort(key=lambda report: not report.implemented)

    risk = compute_risk(session, scoring_run)
    return RepositoryReport(
        repository_id=repository.id,  # type: ignore[arg-type]
        repository_name=repository.name,
        scoring_run_id=scoring_run.id,  # type: ignore[arg-type]
        commit_sha=audit.commit_sha,
        audited_at=audit.audited_at,
        scored_at=scoring_run.scored_at,
        categories=category_reports,
        risk=risk,
        risk_index=sum(entry.weighted for entry in risk),
    )


@router.get(
    "/{repository_id}/report/criteria/{criterion_id}/findings",
    response_model=list[FindingReport],
)
def list_criterion_findings(
    repository_id: int,
    criterion_id: int,
    scoring_run_id: int | None = None,
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[FindingReport]:
    """Return one page of a criterion's findings, in report order, starting at `offset`.

    The report holds the first page of each criterion; this endpoint serves the next ones,
    from the requested or latest scoring run. An offset past the end returns an empty list.
    """
    if session.get(Repository, repository_id) is None:
        raise HTTPException(status_code=404, detail="repository not found")
    if session.get(Criterion, criterion_id) is None:
        raise HTTPException(status_code=404, detail="criterion not found")
    scoring_run = _resolve_scoring_run(session, repository_id, scoring_run_id)
    if scoring_run is None:
        raise HTTPException(status_code=404, detail="no score found for this repository")
    return _findings_page(session, scoring_run.id, criterion_id, offset)  # type: ignore[arg-type]


@router.get("/{repository_id}/badge", response_model=BadgeResponse)
def get_repository_badge(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> BadgeResponse:
    """Return a shields.io badge with the latest global score, or a grey placeholder if unscored."""
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
