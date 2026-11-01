"""Normalizer scoring complexity hotspots across the complexity tools."""

from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.finding_fingerprint import compute_fingerprint
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.cyclomatic_complexity import _extract_blocks, _has_usable_payload
from radar_audit.normalizers.shared import add_finding_with_recommendation

_USABLE_EXIT_CODES_BY_TOOL = {
    "radon-cc": {0},
    "eslint-complexity": {0, 1},
    "phpmd-codesize": {0, 2},
}
_OUTLIER_COMPLEXITY_THRESHOLD = 10
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (2, 8.0), (5, 6.0), (10, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0
_RECOMMENDATION_TEXT = (
    "This function is a complexity hotspot: prioritize refactoring it over "
    "lower-complexity functions elsewhere in the codebase."
)


def normalize_complexity_hotspots(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score complexity hotspots by counting functions above the outlier complexity threshold."""
    relevant = [
        r
        for r in tool_results
        if r.exit_code in _USABLE_EXIT_CODES_BY_TOOL.get(r.tool_name, set())
        and _has_usable_payload(r)
    ]
    if not relevant:
        return None

    worst_value: float | None = None
    worst_confidence: Confidence | None = None
    for tool_result in relevant:
        blocks = _extract_blocks(tool_result)
        outliers = [
            block for block in blocks if int(block["complexity"]) > _OUTLIER_COMPLEXITY_THRESHOLD
        ]
        tool_confidence = _confidence_for_tool(tool_result.tool_name)
        for block in outliers:
            description = (
                f"{block.get('name', 'function')} has cyclomatic complexity {block['complexity']}"
            )
            add_finding_with_recommendation(
                session,
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.MEDIUM,
                    description=description,
                    file=block.get("file"),
                    line=block.get("line"),
                    magnitude=float(block["complexity"]),
                    # Same label convention as 2.3's finding for the same block
                    # (qualified name, not the volatile complexity value), but a
                    # different criterion_id -- so this fingerprint is distinct
                    # from 2.3's for the exact same function, by design.
                    fingerprint=compute_fingerprint(
                        criterion.id,
                        FindingSeverity.MEDIUM,
                        block.get("file"),
                        block.get("name") or "function",
                    ),
                    confidence=tool_confidence,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                ),
                _RECOMMENDATION_TEXT,
            )
        value = _band_value(len(outliers))
        if worst_value is None or value < worst_value:
            worst_value = value
            worst_confidence = tool_confidence

    if worst_value is None or worst_confidence is None:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=worst_value,
        confidence=worst_confidence,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(outlier_count: int) -> float:
    for max_count, value in _BANDS:
        if outlier_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _confidence_for_tool(tool_name: str) -> Confidence:
    return Confidence.HIGH if tool_name == "radon-cc" else Confidence.MEDIUM
