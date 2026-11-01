"""Markdown report rendering and writing for a scored repository."""

from __future__ import annotations

from pathlib import Path

from radar_core.enums import ScoreLevel
from radar_core.finding_ordering import sort_findings_by_priority
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_audit.scoring import get_repository_by_name


class NoScoringRunFoundError(ValueError):
    """Raised when a Repository has no ScoringRun row yet."""


def _get_latest_scoring_run(
    session: Session, repository_id: int, repository_name: str
) -> ScoringRun:
    scoring_run = session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()
    if scoring_run is None:
        msg = (
            f"No score found for {repository_name!r} -- run 'radar-audit score "
            f"{repository_name}' first"
        )
        raise NoScoringRunFoundError(msg)
    return scoring_run


def render_report(session: Session, repo_name: str) -> str:
    """Render a repository's latest scoring run as Markdown, grouped by category and criterion."""
    repository = get_repository_by_name(session, repo_name)
    assert repository.id is not None
    scoring_run = _get_latest_scoring_run(session, repository.id, repository.name)
    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None

    categories, category_scores, criterion_scores = _fetch_categories_and_scores(
        session, scoring_run
    )
    findings_by_criterion, recommendation_by_finding = _fetch_findings_data(session, scoring_run)

    lines = [
        f"# Report: {repository.name}",
        "",
        f"- Commit: `{audit.commit_sha}`",
        f"- Audited at: {audit.audited_at.isoformat()}",
        f"- Scored at: {scoring_run.scored_at.isoformat()}",
        "",
    ]

    for category in categories:
        lines.extend(
            _render_category_block(
                session,
                category,
                category_scores.get(category.id),
                criterion_scores,
                findings_by_criterion,
                recommendation_by_finding,
            )
        )

    return "\n".join(lines).rstrip() + "\n"


def _fetch_categories_and_scores(
    session: Session, scoring_run: ScoringRun
) -> tuple[list[Category], dict[int | None, Score], dict[int | None, Score]]:
    categories = session.exec(
        select(Category)
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(Category.order)  # type: ignore[arg-type]
    ).all()

    scores = session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    category_scores = {s.category_id: s for s in scores if s.level == ScoreLevel.CATEGORY}
    criterion_scores = {s.criterion_id: s for s in scores if s.level == ScoreLevel.CRITERION}
    return list(categories), category_scores, criterion_scores


def _fetch_findings_data(
    session: Session, scoring_run: ScoringRun
) -> tuple[dict[int | None, list[Finding]], dict[int | None, Recommendation]]:
    findings = session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    findings_by_criterion: dict[int | None, list[Finding]] = {}
    for finding in sort_findings_by_priority(findings):
        findings_by_criterion.setdefault(finding.criterion_id, []).append(finding)

    finding_ids = [f.id for f in findings if f.id is not None]
    recommendations = session.exec(
        select(Recommendation).where(Recommendation.finding_id.in_(finding_ids))  # type: ignore[attr-defined]
    ).all()
    recommendation_by_finding: dict[int | None, Recommendation] = {
        r.finding_id: r for r in recommendations
    }
    return findings_by_criterion, recommendation_by_finding


def _render_category_header(category: Category, category_score: Score | None) -> str:
    if category_score is None:
        return f"## {category.order}. {category.name} -- Not yet audited"
    return (
        f"## {category.order}. {category.name} -- {category_score.value:.1f}/10 "
        f"({category_score.confidence.value} confidence)"
    )


def _render_criterion_status_line(criterion: Criterion, criterion_score: Score | None) -> str:
    if criterion_score is None:
        return f"- {criterion.name}: not scored this run"
    if criterion_score.na_reason is not None:
        return f"- {criterion.name}: N/A -- {criterion_score.na_reason}"
    return f"- {criterion.name}: {criterion_score.value:.1f}/10"


def _render_finding_lines(
    finding: Finding, recommendation_by_finding: dict[int | None, Recommendation]
) -> list[str]:
    lines = [f"  - [{finding.severity.value}] {finding.description}{_finding_location(finding)}"]
    recommendation = recommendation_by_finding.get(finding.id)
    if recommendation is not None:
        lines.append(f"    -> {recommendation.text}")
    return lines


def _render_category_block(
    session: Session,
    category: Category,
    category_score: Score | None,
    criterion_scores: dict[int | None, Score],
    findings_by_criterion: dict[int | None, list[Finding]],
    recommendation_by_finding: dict[int | None, Recommendation],
) -> list[str]:
    lines = [_render_category_header(category, category_score)]

    criteria = session.exec(
        select(Criterion).where(Criterion.category_id == category.id).order_by(Criterion.id)  # type: ignore[arg-type]
    ).all()
    for criterion in criteria:
        criterion_score = criterion_scores.get(criterion.id)
        lines.append(_render_criterion_status_line(criterion, criterion_score))
        for finding in findings_by_criterion.get(criterion.id, []):
            lines.extend(_render_finding_lines(finding, recommendation_by_finding))
    lines.append("")
    return lines


def _finding_location(finding: Finding) -> str:
    if finding.file is None:
        return ""
    if finding.line is None:
        return f" ({finding.file})"
    return f" ({finding.file}:{finding.line})"


def write_report(markdown: str, repo_name: str, output_dir: Path) -> Path:
    """Write the Markdown report to output_dir/<repo_name>/latest.md and return that path."""
    target_dir = output_dir / repo_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "latest.md"
    target_path.write_text(markdown)
    return target_path
