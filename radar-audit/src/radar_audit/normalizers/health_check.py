from __future__ import annotations

from pathlib import Path

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import find_prod_compose, get_repository_path, iter_source_files

_HEALTH_PATH_MARKERS = ("/health", "/healthz")

_NO_LONG_LIVED_SERVICE_NA_REASON = "No production compose file found (no long-lived service)"
_FOUND_VALUE = 10.0
_NOT_FOUND_VALUE = 0.0


def normalize_health_check(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)

    # Same N/A reasoning as D11 (criterion 7.2): no production compose file
    # means no evidence of a long-lived deployed service, so a health-check
    # endpoint isn't a meaningful concept for this repo.
    if find_prod_compose(target_path) is None:
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            # Same numeric value as _NOT_FOUND_VALUE below, intentionally: both
            # states render as "no credit", N/A vs. a real gap is distinguished
            # by na_reason, not by the score value.
            value=_NOT_FOUND_VALUE,
            confidence=Confidence.HIGH,
            na_reason=_NO_LONG_LIVED_SERVICE_NA_REASON,
        )
    else:
        value = _FOUND_VALUE if _has_health_route(target_path) else _NOT_FOUND_VALUE
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=value,
            confidence=Confidence.MEDIUM,
        )

    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _has_health_route(target_path: Path) -> bool:
    for file_path in iter_source_files(target_path):
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(marker in text for marker in _HEALTH_PATH_MARKERS):
            return True
    return False
