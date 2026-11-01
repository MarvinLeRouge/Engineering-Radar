"""Normalizer scoring end-to-end test setup and CI wiring from Playwright presence."""

from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_finding_with_recommendation

_TODO, _IN_PROGRESS, _DONE = 0, 1, 2
_VALUE_BY_STATUS = {_TODO: 0.0, _IN_PROGRESS: 5.0, _DONE: 10.0}
_RECOMMENDATION_TEXT_MISSING = "Add Playwright end-to-end tests covering the main user flows."
_RECOMMENDATION_TEXT_NOT_WIRED = "Wire the existing Playwright suite into a CI workflow."


def normalize_e2e_tests(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score end-to-end test coverage from Playwright presence and whether CI runs it."""
    playwright_results = [
        r for r in tool_results if r.tool_name == "playwright-presence" and r.exit_code == 0
    ]
    if not playwright_results:
        # No javascript sub-project ran PlaywrightPresenceRunner at all -> N/A.
        return None

    worst_status = _worst_playwright_status(tool_results, playwright_results)
    _add_status_finding(session, scoring_run, criterion, playwright_results[0], worst_status)

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_VALUE_BY_STATUS[worst_status],
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _status_for(present: bool, ci_wired: bool) -> int:
    if not present:
        return _TODO
    return _DONE if ci_wired else _IN_PROGRESS


def _worst_playwright_status(
    tool_results: list[ToolResult], playwright_results: list[ToolResult]
) -> int:
    ci_results = [r for r in tool_results if r.tool_name == "ci-workflow" and r.exit_code == 0]
    ci_wired = bool(
        ci_results and ci_results[0].raw_output.get("playwright_execution_found", False)
    )
    # Worst-status-wins across every javascript sub-project (spec section 7).
    return min(
        _status_for(bool(r.raw_output.get("present", False)), ci_wired) for r in playwright_results
    )


def _add_status_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    worst_status: int,
) -> None:
    if worst_status == _TODO:
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            FindingSeverity.MEDIUM,
            "Repo is web-facing but has no Playwright E2E test setup",
            _RECOMMENDATION_TEXT_MISSING,
        )
    elif worst_status == _IN_PROGRESS:
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            FindingSeverity.LOW,
            "Playwright is present but not wired into any CI workflow",
            _RECOMMENDATION_TEXT_NOT_WIRED,
        )


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    severity: FindingSeverity,
    description: str,
    recommendation_text: str,
) -> None:
    add_finding_with_recommendation(
        session,
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=severity,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        ),
        recommendation_text,
    )
