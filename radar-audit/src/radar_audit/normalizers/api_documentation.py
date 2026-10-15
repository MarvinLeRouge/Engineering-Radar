from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.discovery import discover_subprojects
from radar_audit.normalizers.shared import (
    composer_dependency_names,
    get_repository_path,
    python_dependency_names,
)

_FASTAPI_PACKAGE = "fastapi"
_L5_SWAGGER_PACKAGE = "darkaonline/l5-swagger"
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

    has_fastapi = _FASTAPI_PACKAGE in python_dependency_names(candidate_dirs)
    has_l5_swagger = _L5_SWAGGER_PACKAGE in composer_dependency_names(candidate_dirs)

    if has_fastapi or has_l5_swagger:
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
