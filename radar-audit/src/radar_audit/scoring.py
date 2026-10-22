from __future__ import annotations

from datetime import UTC, datetime

from radar_core.enums import Confidence, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_audit.normalizers import CRITERION_NORMALIZERS
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.roadmap_promotion import promote_improvement_tasks
from radar_audit.taxonomy.seed import seed_taxonomy

_CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


class RepositoryNotFoundError(ValueError):
    """Raised when no Repository row exists for the given name."""


class NoAuditFoundError(ValueError):
    """Raised when a Repository has no Audit row yet."""


def get_repository_by_name(session: Session, repo_name: str) -> Repository:
    repository = session.exec(select(Repository).where(Repository.name == repo_name)).first()
    if repository is None:
        raise RepositoryNotFoundError(
            f"No repository named {repo_name!r} -- run 'radar-audit run {repo_name}' first"
        )
    return repository


def _get_latest_audit(session: Session, repository: Repository) -> Audit:
    audit = session.exec(
        select(Audit).where(Audit.repository_id == repository.id).order_by(desc(Audit.audited_at))  # type: ignore[arg-type]
    ).first()
    if audit is None:
        raise NoAuditFoundError(
            f"No audit found for {repository.name!r} -- run 'radar-audit run "
            f"{repository.name}' first"
        )
    return audit


def score_repository(session: Session, repo_name: str) -> ScoringRun:
    repository = get_repository_by_name(session, repo_name)
    audit = _get_latest_audit(session, repository)
    methodology_version = seed_taxonomy(session)
    scoring_run = get_or_create_scoring_run(session, audit, methodology_version)

    existing_scores = session.exec(
        select(Score).where(Score.scoring_run_id == scoring_run.id)
    ).all()
    for existing in existing_scores:
        session.delete(existing)

    existing_findings = session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    carried_verdicts = _collect_carried_verdicts(session, repository)
    existing_finding_ids = [f.id for f in existing_findings if f.id is not None]
    existing_recommendations = session.exec(
        select(Recommendation).where(Recommendation.finding_id.in_(existing_finding_ids))  # type: ignore[attr-defined]
    ).all()
    for existing_recommendation in existing_recommendations:
        session.delete(existing_recommendation)
    existing_task_links = session.exec(
        select(FindingImprovementTaskLink).where(
            FindingImprovementTaskLink.finding_id.in_(existing_finding_ids)  # type: ignore[attr-defined]
        )
    ).all()
    for existing_task_link in existing_task_links:
        session.delete(existing_task_link)
    # Flush the Recommendation/link deletes before deleting their parent Findings:
    # SQLAlchemy's unit of work does not infer delete ordering across unrelated mapped
    # classes (no relationship() is declared between Finding and either of them), so
    # without this the DELETE statements can be batched in an order that violates the
    # FK constraint.
    session.flush()
    for existing_finding in existing_findings:
        session.delete(existing_finding)

    scoring_run.scored_at = datetime.now(UTC)
    session.add(scoring_run)
    session.commit()

    tool_results = list(session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)))

    methodology_version_id = methodology_version.id
    assert methodology_version_id is not None

    scored_by_category: dict[int, list[tuple[Criterion, Score]]] = {}
    for (category_name, criterion_name), normalizer in CRITERION_NORMALIZERS.items():
        criterion = get_criterion(session, methodology_version_id, category_name, criterion_name)
        score = normalizer(session, scoring_run, criterion, tool_results)
        if score is None or score.na_reason is not None:
            continue
        scored_by_category.setdefault(criterion.category_id, []).append((criterion, score))

    _carry_forward_human_verdicts(session, scoring_run, carried_verdicts)
    promote_improvement_tasks(session, scoring_run)

    category_scores: list[tuple[Category, Score]] = []
    for category_id, pairs in scored_by_category.items():
        category = session.get(Category, category_id)
        assert category is not None
        category_score = _write_category_score(session, scoring_run, category, pairs)
        category_scores.append((category, category_score))

    _write_global_score(session, scoring_run, category_scores)

    return scoring_run


def _collect_carried_verdicts(
    session: Session, repository: Repository
) -> dict[str, tuple[FindingStatus, HumanVerdict]]:
    """Collect the most recent human-set status/verdict per fingerprint, across every
    `ScoringRun` this repository has ever had -- not just the current one.

    A new commit gets a brand-new `Audit` and therefore a brand-new `ScoringRun`
    (keyed on `(audit_id, methodology_version_id)`), whose own `Finding` rows start
    out empty: scoping this lookup to only the current `scoring_run.id` would make
    carry-forward a no-op on every real re-audit, the exact case it exists for.
    Ordered by `ScoringRun.scored_at` ascending, so a dict comprehension's
    last-write-wins semantics keep the most recent verdict per fingerprint.
    """
    historical_findings = session.exec(
        select(Finding)
        .join(ScoringRun, ScoringRun.id == Finding.scoring_run_id)  # type: ignore[arg-type]
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository.id)
        .order_by(ScoringRun.scored_at)  # type: ignore[arg-type]
    ).all()
    return {
        finding.fingerprint: (finding.status, finding.human_verdict)
        for finding in historical_findings
        if finding.fingerprint is not None
        and (
            finding.status != FindingStatus.OPEN or finding.human_verdict != HumanVerdict.UNREVIEWED
        )
    }


def _carry_forward_human_verdicts(
    session: Session,
    scoring_run: ScoringRun,
    carried_verdicts: dict[str, tuple[FindingStatus, HumanVerdict]],
) -> None:
    if not carried_verdicts:
        return
    new_findings = session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    for finding in new_findings:
        if finding.fingerprint is None:
            continue
        verdict = carried_verdicts.get(finding.fingerprint)
        if verdict is None:
            continue
        finding.status, finding.human_verdict = verdict
        session.add(finding)
    session.commit()


def _write_category_score(
    session: Session,
    scoring_run: ScoringRun,
    category: Category,
    pairs: list[tuple[Criterion, Score]],
) -> Score:
    total_weight = sum(criterion.weight for criterion, _ in pairs)
    weighted_sum = sum(criterion.weight * score.value for criterion, score in pairs)
    value = weighted_sum / total_weight
    confidence = max((score.confidence for _, score in pairs), key=lambda c: _CONFIDENCE_RANK[c])

    category_score = Score(
        scoring_run_id=scoring_run.id,
        category_id=category.id,
        level=ScoreLevel.CATEGORY,
        value=value,
        confidence=confidence,
    )
    session.add(category_score)
    session.commit()
    session.refresh(category_score)
    return category_score


def _write_global_score(
    session: Session,
    scoring_run: ScoringRun,
    category_scores: list[tuple[Category, Score]],
) -> None:
    """Weighted average of category scores by category.weight, same pattern as
    _write_category_score's criterion-to-category aggregation one level up.

    Left as None (not 0) when no category was scored at all -- a repository
    with nothing yet audited has no global score, not the worst one.
    """
    if not category_scores:
        return

    total_weight = sum(category.weight for category, _ in category_scores)
    weighted_sum = sum(category.weight * score.value for category, score in category_scores)
    scoring_run.global_score = weighted_sum / total_weight
    scoring_run.global_confidence = max(
        (score.confidence for _, score in category_scores), key=lambda c: _CONFIDENCE_RANK[c]
    )
    session.add(scoring_run)
    session.commit()
    session.refresh(scoring_run)
