from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.discovery import discover_subprojects
from radar_audit.normalizers.shared import get_repository_path

_FASTAPI_PACKAGE = "fastapi"
_PHP_MANIFEST_FILENAME = "composer.json"
_L5_SWAGGER_PACKAGE = "darkaonline/l5-swagger"
_PACKAGE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")
# Archetype C per the Quality Framework: only FastAPI and Laravel L5-Swagger are
# validated candidates. A repo with an API via another framework (Flask,
# Express, ...) also falls into this N/A branch, same as other criteria with
# no validated candidate tool for a given stack.
_NO_API_DOC_TOOLING_NA_REASON = (
    "No FastAPI or Laravel L5-Swagger API documentation tooling detected"
)


def normalize_api_documentation(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)
    # A monorepo-style repo (e.g. separate backend/frontend subprojects) keeps
    # its manifest one level below the repo root, not at the root itself.
    # De-duplicated: discover_subprojects yields the same directory once per
    # detected stack, so a dir with both a Python and a PHP manifest would
    # otherwise be scanned twice.
    candidate_dirs = sorted({subproject.path for subproject in discover_subprojects(target_path)})

    if _has_fastapi(candidate_dirs) or _has_l5_swagger(candidate_dirs):
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=10.0,
            confidence=Confidence.MEDIUM,
        )
    else:
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=0.0,
            confidence=Confidence.HIGH,
            na_reason=_NO_API_DOC_TOOLING_NA_REASON,
        )

    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _package_name(spec: str) -> str:
    match = _PACKAGE_NAME_PATTERN.match(spec.strip())
    return match.group(0).lower() if match else ""


def _pyproject_dependency_names(data: dict[str, object]) -> set[str]:
    names: set[str] = set()

    project = data.get("project")
    if isinstance(project, dict):
        dependencies = project.get("dependencies")
        if isinstance(dependencies, list):
            names.update(_package_name(dep) for dep in dependencies if isinstance(dep, str))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    names.update(_package_name(dep) for dep in group if isinstance(dep, str))

    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            dependencies = poetry.get("dependencies")
            if isinstance(dependencies, dict):
                names.update(key.lower() for key in dependencies)

    return names


def _has_fastapi(candidate_dirs: list[Path]) -> bool:
    for directory in candidate_dirs:
        pyproject_path = directory / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                data = tomllib.loads(pyproject_path.read_text())
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
                data = None
            if isinstance(data, dict) and _FASTAPI_PACKAGE in _pyproject_dependency_names(data):
                return True

        requirements_path = directory / "requirements.txt"
        if requirements_path.is_file():
            try:
                lines = requirements_path.read_text().splitlines()
            except (OSError, UnicodeDecodeError):
                lines = []
            if any(
                _package_name(line) == _FASTAPI_PACKAGE
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ):
                return True
    return False


def _has_l5_swagger(candidate_dirs: list[Path]) -> bool:
    for directory in candidate_dirs:
        manifest_path = directory / _PHP_MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        try:
            data = json.loads(manifest_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue

        deps: dict[str, object] = {}
        for key in ("require", "require-dev"):
            section = data.get(key)
            if isinstance(section, dict):
                deps.update(section)
        if _L5_SWAGGER_PACKAGE in deps:
            return True
    return False
