from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_finding_with_recommendation

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

    for finding in findings_payload:
        add_finding_with_recommendation(
            session,
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.LOW,
                description=finding.get("message", "actionlint finding"),
                file=finding.get("filepath"),
                line=finding.get("line"),
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            ),
            _RECOMMENDATION_TEXT,
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(len(findings_payload)),
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
