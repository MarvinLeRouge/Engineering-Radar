# radar-audit/src/radar_audit/normalizers/traefik_parity.py
from __future__ import annotations

from pathlib import Path

import yaml
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_finding_with_recommendation, get_repository_path

_LOCAL_COMPOSE_FILENAME = "docker-compose.yml"
_PROD_COMPOSE_CANDIDATES = (
    "docker-compose.prod.yml",
    "docker-compose.production.yml",
    "compose.prod.yml",
    "compose.prod.yaml",
)
_NO_PROD_FILE_NA_REASON = "No production compose file found (no long-lived service to proxy)"
_NO_TRAEFIK_NA_REASON = "No Traefik-routed services found in either compose file"


def normalize_traefik_parity(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)

    local_services = _traefik_services(target_path / _LOCAL_COMPOSE_FILENAME)
    if local_services is None:
        return None

    prod_path = _find_prod_compose(target_path)
    if prod_path is None:
        return _na_score(session, scoring_run, criterion, _NO_PROD_FILE_NA_REASON)

    prod_services = _traefik_services(prod_path)
    if prod_services is None:
        return _na_score(session, scoring_run, criterion, _NO_PROD_FILE_NA_REASON)

    both = local_services & prod_services
    union = local_services | prod_services
    if not union:
        return _na_score(session, scoring_run, criterion, _NO_TRAEFIK_NA_REASON)

    for service in sorted(union - both):
        missing_side = "prod" if service in local_services else "local"
        add_finding_with_recommendation(
            session,
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                severity=FindingSeverity.LOW,
                description=(
                    f"Service '{service}' is Traefik-routed but missing a {missing_side} router"
                ),
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            ),
            f"Add matching Traefik labels for '{service}' to the {missing_side} compose file.",
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(len(both) / len(union)) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _na_score(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, reason: str
) -> Score:
    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=0.0,
        confidence=Confidence.HIGH,
        na_reason=reason,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _find_prod_compose(target_path: Path) -> Path | None:
    for candidate in _PROD_COMPOSE_CANDIDATES:
        candidate_path = target_path / candidate
        if candidate_path.is_file():
            return candidate_path
    return None


def _traefik_services(compose_path: Path) -> set[str] | None:
    if not compose_path.is_file():
        return None
    try:
        data = yaml.safe_load(compose_path.read_text())
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    services = data.get("services")
    if not isinstance(services, dict):
        return set()

    result: set[str] = set()
    for name, definition in services.items():
        if not isinstance(definition, dict):
            continue
        labels = definition.get("labels") or []
        if isinstance(labels, dict):
            labels = [f"{k}={v}" for k, v in labels.items()]
        if any(
            str(label).strip().strip('"').strip("'") == "traefik.enable=true" for label in labels
        ):
            result.add(name)
    return result
