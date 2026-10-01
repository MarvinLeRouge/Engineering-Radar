from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import has_success_payload

_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (3, 8.0), (8, 6.0), (15, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_container_build_hardening(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "hadolint" and has_success_payload(r, "dockerfiles")
    ]
    if not relevant:
        return None

    total = 0
    finding_count = 0
    for tool_result in relevant:
        for entry in tool_result.raw_output["dockerfiles"]:
            findings = entry.get("findings")
            # A Dockerfile hadolint failed to lint carries an "error" key instead of a
            # findings list: it is excluded from the count rather than treated as clean.
            if not isinstance(findings, list) or "error" in entry:
                continue
            total += 1
            finding_count += len(findings)

    if total == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(finding_count),
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(finding_count: int) -> float:
    for max_count, value in _BANDS:
        if finding_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE
