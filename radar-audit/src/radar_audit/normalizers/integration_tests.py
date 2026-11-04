"""Normalizer scoring integration test presence from test file heuristics."""

from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_repo_level_finding, save_criterion_score

_BAND_UPPER_BOUNDS = (0.0, 10.0, 25.0, 50.0)


def normalize_integration_tests(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score integration test presence from the ratio of integration to total test files."""
    relevant = [
        r for r in tool_results if r.tool_name == "integration-test-heuristic" and r.exit_code == 0
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    total = tool_result.raw_output.get("total_test_files", 0)
    if total == 0:
        # No tests at all is already carried by criterion 3.1 -- not penalized twice.
        return None

    integration = tool_result.raw_output.get("integration_test_files", 0)
    ratio_percent = (integration / total) * 100
    value = _band_value(ratio_percent)
    if value < 10.0:
        target = next(bound for bound in _BAND_UPPER_BOUNDS if ratio_percent <= bound)
        add_repo_level_finding(
            session,
            scoring_run,
            criterion,
            FindingSeverity.MEDIUM if integration == 0 else FindingSeverity.LOW,
            f"{integration} of {total} test files are integration tests ({ratio_percent:.0f}%)",
            "Add integration tests exercising real components together; the next band "
            f"starts above {target:.0f}% of test files (above 50% scores 10).",
            "integration-test-ratio-below-target",
        )

    return save_criterion_score(session, scoring_run, criterion, value, Confidence.MEDIUM)


def _band_value(ratio_percent: float) -> float:
    # Bands: 0%->0, 0-10%->4, 10-25%->6, 25-50%->8, >50%->10 (spec §3.4). Resolved
    # during design but provisional -- not yet calibrated against real portfolio data
    # (spec §11), same discipline as every prior increment's thresholds.
    if ratio_percent <= 0.0:
        return 0.0
    if ratio_percent <= 10.0:
        return 4.0
    if ratio_percent <= 25.0:
        return 6.0
    if ratio_percent <= 50.0:
        return 8.0
    return 10.0
