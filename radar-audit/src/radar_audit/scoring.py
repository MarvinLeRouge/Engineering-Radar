"""Scoring of a repository's latest audit into per-criterion, category and global scores."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.finding_fingerprint import compute_fingerprint
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc, func
from sqlmodel import Session, select

from radar_audit.normalizers import CRITERION_NORMALIZERS
from radar_audit.normalizers.shared import (
    get_criterion,
    get_or_create_scoring_run,
    set_dismissed_fingerprints,
)
from radar_audit.roadmap_promotion import promote_improvement_tasks
from radar_audit.taxonomy.seed import seed_taxonomy, sync_implemented_criteria

log = structlog.get_logger("radar_audit.scoring")

# Human status, verdict and note of one fingerprint, as carried to the next scoring run.
CarriedVerdict = tuple[FindingStatus, HumanVerdict, str | None]

_CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


class RepositoryNotFoundError(ValueError):
    """Raised when no Repository row exists for the given name."""


class NoAuditFoundError(ValueError):
    """Raised when a Repository has no Audit row yet."""


def get_repository_by_name(session: Session, repo_name: str) -> Repository:
    """Return the Repository row named repo_name, raising if none exists."""
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
    """Score a repository's latest audit, carrying human verdicts forward from earlier runs."""
    repository = get_repository_by_name(session, repo_name)
    audit = _get_latest_audit(session, repository)
    methodology_version = seed_taxonomy(session)
    _sync_implemented(session, methodology_version)
    scoring_run = get_or_create_scoring_run(session, audit, methodology_version)

    carried_verdicts = _collect_carried_verdicts(session, repository)
    set_dismissed_fingerprints(
        session,
        {
            fingerprint
            for fingerprint, (_, verdict, _) in carried_verdicts.items()
            if verdict == HumanVerdict.FALSE_POSITIVE
        },
    )
    try:
        with structlog.contextvars.bound_contextvars(audit_id=audit.id):
            scored = _score_run(session, audit, methodology_version, scoring_run, carried_verdicts)
            log.info(
                "scoring_finished",
                repo=repo_name,
                global_score=scored.global_score,
                findings=session.exec(
                    select(func.count()).where(Finding.scoring_run_id == scored.id)
                ).one(),
            )
            return scored
    finally:
        set_dismissed_fingerprints(session, set())


def _sync_implemented(session: Session, methodology_version: MethodologyVersion) -> None:
    """Record which criteria radar-audit can score, so the API can tell "not implemented"."""
    sync_implemented_criteria(session, methodology_version, set(CRITERION_NORMALIZERS))


def _score_run(
    session: Session,
    audit: Audit,
    methodology_version: MethodologyVersion,
    scoring_run: ScoringRun,
    carried_verdicts: dict[str, CarriedVerdict],
) -> ScoringRun:
    existing_findings = session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    _wipe_scoring_run_data(session, scoring_run, existing_findings)

    scoring_run.scored_at = datetime.now(UTC)
    session.add(scoring_run)
    session.commit()

    tool_results = list(session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)))
    scored_by_category = _run_normalizers(session, scoring_run, methodology_version, tool_results)

    _carry_forward_human_verdicts(session, scoring_run, carried_verdicts)
    promote_improvement_tasks(session, scoring_run)

    category_scores = _write_category_scores(session, scoring_run, scored_by_category)
    _write_global_score(session, scoring_run, category_scores)

    return scoring_run


def _wipe_scoring_run_data(
    session: Session, scoring_run: ScoringRun, existing_findings: Sequence[Finding]
) -> None:
    existing_scores = session.exec(
        select(Score).where(Score.scoring_run_id == scoring_run.id)
    ).all()
    for existing in existing_scores:
        session.delete(existing)

    # A subquery, not a list of ids: SQLite caps bound parameters (32766) per statement.
    existing_finding_ids = select(Finding.id).where(Finding.scoring_run_id == scoring_run.id)
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


def _run_normalizers(
    session: Session,
    scoring_run: ScoringRun,
    methodology_version: MethodologyVersion,
    tool_results: list[ToolResult],
) -> dict[int, list[tuple[Criterion, Score]]]:
    methodology_version_id = methodology_version.id
    assert methodology_version_id is not None

    scored_by_category: dict[int, list[tuple[Criterion, Score]]] = {}
    for (category_name, criterion_name), normalizer in CRITERION_NORMALIZERS.items():
        criterion = get_criterion(session, methodology_version_id, category_name, criterion_name)
        score = normalizer(session, scoring_run, criterion, tool_results)
        if score is None or score.na_reason is not None:
            continue
        scored_by_category.setdefault(criterion.category_id, []).append((criterion, score))
    return scored_by_category


def _write_category_scores(
    session: Session,
    scoring_run: ScoringRun,
    scored_by_category: dict[int, list[tuple[Criterion, Score]]],
) -> list[tuple[Category, Score]]:
    category_scores: list[tuple[Category, Score]] = []
    for category_id, pairs in scored_by_category.items():
        category = session.get(Category, category_id)
        assert category is not None
        category_score = _write_category_score(session, scoring_run, category, pairs)
        category_scores.append((category, category_score))
    return category_scores


def _collect_carried_verdicts(
    session: Session, repository: Repository
) -> dict[str, CarriedVerdict]:
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
    image_subprojects = _legacy_image_subprojects(session, repository)
    latest: dict[str, CarriedVerdict] = {}
    for finding in historical_findings:
        fingerprint = _current_fingerprint(finding, image_subprojects)
        if fingerprint is not None:
            latest[fingerprint] = (finding.status, finding.human_verdict, finding.verdict_note)
    # Filter only after last-write-wins: a verdict reverted to OPEN/UNREVIEWED on a
    # later run must override the older human verdict, not be skipped in favor of it.
    return {
        fingerprint: verdict
        for fingerprint, verdict in latest.items()
        if verdict[:2] != (FindingStatus.OPEN, HumanVerdict.UNREVIEWED)
    }


def _legacy_image_subprojects(session: Session, repository: Repository) -> dict[int, str]:
    """Map each fileless trivy-image finding of the repository to its image's subproject.

    shortcut: container image findings stored before FIX-025 have no file and a
    fingerprint without their image; drop this once every repository has been
    re-scored, since the newer per-image rows then carry the verdicts.
    """
    rows = session.exec(
        select(Finding.id, ToolResult.subproject_path)
        .join(ToolResult, ToolResult.id == Finding.tool_result_id)  # type: ignore[arg-type]
        .join(Audit, Audit.id == ToolResult.audit_id)  # type: ignore[arg-type]
        .where(
            Audit.repository_id == repository.id,
            ToolResult.tool_name == "trivy-image",
            Finding.file.is_(None),  # type: ignore[union-attr]
        )
    ).all()
    return {finding_id: subproject for finding_id, subproject in rows if finding_id is not None}


def _current_fingerprint(finding: Finding, image_subprojects: dict[int, str]) -> str | None:
    """The finding's fingerprint, recomputed with its image for a pre-FIX-025 image finding."""
    subproject = image_subprojects.get(finding.id) if finding.id is not None else None
    if subproject is None:
        return finding.fingerprint
    return compute_fingerprint(
        finding.criterion_id, FindingSeverity(finding.severity), subproject, finding.description
    )


def _carry_forward_human_verdicts(
    session: Session,
    scoring_run: ScoringRun,
    carried_verdicts: dict[str, CarriedVerdict],
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
        finding.status, finding.human_verdict, finding.verdict_note = verdict
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
