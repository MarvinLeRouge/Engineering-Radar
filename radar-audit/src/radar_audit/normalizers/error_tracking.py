from __future__ import annotations

import re
from pathlib import Path

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.discovery import discover_subprojects
from radar_audit.normalizers.shared import (
    composer_dependency_names,
    get_repository_path,
    iter_source_files,
    npm_dependency_names,
    python_dependency_names,
)

_SENTRY_PYTHON_PACKAGE = "sentry-sdk"
_SENTRY_JS_PACKAGE_PREFIX = "@sentry/"
_SENTRY_PHP_PACKAGE = "sentry/sentry-laravel"

# Captures to end-of-line rather than stopping at the first "," or ")" -- a
# nested call like dsn=os.getenv("SENTRY_DSN") has its own closing paren
# before the assignment's, which would otherwise truncate the capture before
# the env-var marker. Trailing text past the real value is harmless here: the
# caller only substring-checks the capture for an env-var marker.
_DSN_PATTERN = re.compile(r"\bdsn\s*[:=]\s*([^\n]+)", re.IGNORECASE)
_ENV_VAR_MARKERS = ("os.getenv", "os.environ", "process.env", "getenv(")

_DONE_VALUE = 10.0
_IN_PROGRESS_VALUE = 5.0
_TODO_VALUE = 0.0


def normalize_error_tracking(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)
    candidate_dirs = sorted({subproject.path for subproject in discover_subprojects(target_path)})

    has_sentry = (
        _SENTRY_PYTHON_PACKAGE in python_dependency_names(candidate_dirs)
        or any(
            name.startswith(_SENTRY_JS_PACKAGE_PREFIX)
            for name in npm_dependency_names(candidate_dirs)
        )
        or _SENTRY_PHP_PACKAGE in composer_dependency_names(candidate_dirs)
    )

    if not has_sentry:
        value = _TODO_VALUE
    elif _has_env_sourced_dsn(target_path):
        value = _DONE_VALUE
    else:
        value = _IN_PROGRESS_VALUE

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


def _has_env_sourced_dsn(target_path: Path) -> bool:
    for file_path in iter_source_files(target_path):
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in _DSN_PATTERN.finditer(text):
            value = match.group(1)
            if any(marker in value for marker in _ENV_VAR_MARKERS):
                return True
    return False
