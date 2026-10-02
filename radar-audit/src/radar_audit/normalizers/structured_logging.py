from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.discovery import discover_subprojects
from radar_audit.normalizers.shared import (
    get_repository_path,
    npm_dependency_names,
    python_dependency_names,
)

# Heuristic per the Quality Framework: a known structured-logging library vs.
# bare print/console.log. PHP has no validated candidate (Monolog ships as
# Laravel's default dependency, so its mere presence is not a meaningful
# signal) -- PHP repos fall through to the "not detected" band, same
# documented limitation as other JS/PHP gaps in this codebase.
_PYTHON_PACKAGES = frozenset({"structlog", "loguru", "python-json-logger", "python-jsonlogger"})
_JS_PACKAGES = frozenset({"winston", "pino", "bunyan"})
_STRUCTURED_VALUE = 10.0
_NOT_DETECTED_VALUE = 4.0


def normalize_structured_logging(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)
    candidate_dirs = sorted({subproject.path for subproject in discover_subprojects(target_path)})

    detected = bool(python_dependency_names(candidate_dirs) & _PYTHON_PACKAGES) or bool(
        npm_dependency_names(candidate_dirs) & _JS_PACKAGES
    )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_STRUCTURED_VALUE if detected else _NOT_DETECTED_VALUE,
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
