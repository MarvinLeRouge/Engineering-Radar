"""Normalizer scoring CI workflow health from actionlint findings."""

from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import (
    add_tool_finding,
    band_value,
    is_dismissed,
    save_criterion_score,
)

_USABLE_EXIT_CODES = {0, 1}
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (3, 8.0), (8, 6.0), (15, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0
_RECOMMENDATION_TEXT = (
    "Fix the actionlint finding (workflow syntax issue or embedded shell-script problem)."
)


def normalize_ci_health(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score CI workflow health from actionlint findings, banded by finding count."""
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "actionlint"
        and r.exit_code in _USABLE_EXIT_CODES
        and isinstance(r.raw_output, dict)
        and isinstance(r.raw_output.get("findings"), list)
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    findings_payload = tool_result.raw_output["findings"]

    counted = 0
    for finding in findings_payload:
        description = finding.get("message", "actionlint finding")
        file = finding.get("filepath")
        added = add_tool_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            severity=FindingSeverity.LOW,
            description=description,
            recommendation_text=_RECOMMENDATION_TEXT,
            confidence=Confidence.HIGH,
            file=file,
            line=finding.get("line"),
        )
        if not is_dismissed(session, added):
            counted += 1

    return save_criterion_score(
        session,
        scoring_run,
        criterion,
        band_value(counted, _BANDS, _ABOVE_HIGHEST_BAND_VALUE),
        Confidence.HIGH,
    )
