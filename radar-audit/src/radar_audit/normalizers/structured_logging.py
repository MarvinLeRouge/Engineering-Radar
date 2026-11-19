"""Normalizer scoring structured logging from logging packages or a PHP JSON formatter."""

from __future__ import annotations

import re
from pathlib import Path

from radar_core.enums import Confidence, FindingSeverity
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.discovery import discover_subprojects
from radar_audit.normalizers.shared import (
    add_repo_level_finding,
    get_repository_path,
    iter_source_files,
    npm_dependency_names,
    python_dependency_names,
    save_criterion_score,
)

# Heuristic per the Quality Framework: a known structured-logging library vs.
# bare print/console.log. For PHP the package says nothing (Monolog ships with
# Laravel), so the signal is a Monolog JSON formatter configured in a
# logging.php config or set as a LOG_*FORMATTER value in an env template.
_PYTHON_PACKAGES = frozenset({"structlog", "loguru", "python-json-logger", "python-jsonlogger"})
_JS_PACKAGES = frozenset({"winston", "pino", "bunyan"})
_PHP_JSON_FORMATTER = re.compile(r"\b(?:JsonFormatter|LogstashFormatter)\b")
# Anchored at line start so a commented-out "# LOG_..." line does not count.
_PHP_ENV_FORMATTER = re.compile(
    r"^LOG_\w*FORMATTER\s*=.*\b(?:JsonFormatter|LogstashFormatter)\b", re.MULTILINE
)
_PHP_CONFIG_EXTENSIONS = frozenset({".php", ".example"})
_STRUCTURED_VALUE = 10.0
_NOT_DETECTED_VALUE = 4.0


def normalize_structured_logging(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score structured logging from a Python or JavaScript structured logging package,
    or a Monolog JSON formatter configured in a PHP project."""
    target_path = get_repository_path(session, scoring_run)
    candidate_dirs = sorted({subproject.path for subproject in discover_subprojects(target_path)})

    detected = (
        bool(python_dependency_names(candidate_dirs) & _PYTHON_PACKAGES)
        or bool(npm_dependency_names(candidate_dirs) & _JS_PACKAGES)
        or _has_php_json_formatter(target_path)
    )
    if not detected:
        add_repo_level_finding(
            session,
            scoring_run,
            criterion,
            FindingSeverity.LOW,
            "No structured logging library detected in any subproject",
            "Log through a structured logging library (structlog or python-json-logger for "
            "Python, pino or winston for JavaScript, a Monolog JsonFormatter for PHP) "
            "instead of bare print/console.log.",
            "no-structured-logging-library",
        )

    return save_criterion_score(
        session,
        scoring_run,
        criterion,
        _STRUCTURED_VALUE if detected else _NOT_DETECTED_VALUE,
        Confidence.MEDIUM,
    )


def _has_php_json_formatter(target_path: Path) -> bool:
    for file_path in iter_source_files(target_path, _PHP_CONFIG_EXTENSIONS):
        if file_path.name == "logging.php":
            pattern = _PHP_JSON_FORMATTER
        elif file_path.name.endswith(".env.example"):
            pattern = _PHP_ENV_FORMATTER
        else:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        if pattern.search(text):
            return True
    return False
