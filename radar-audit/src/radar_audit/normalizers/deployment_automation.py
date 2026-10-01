# radar-audit/src/radar_audit/normalizers/deployment_automation.py
from __future__ import annotations

from pathlib import Path

import yaml
from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import get_repository_path

_CANDIDATE_FILENAMES = frozenset(
    {"build-push.yml", "build-deploy.yml", "deploy.yml", "release.yml"}
)


def normalize_deployment_automation(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)
    workflows_dir = target_path / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return None

    candidates = [
        p for p in workflows_dir.iterdir() if p.is_file() and p.name in _CANDIDATE_FILENAMES
    ]
    if not candidates:
        value = 0.0
    elif any(_is_wired_to_registry_push(p) for p in candidates):
        value = 10.0
    else:
        value = 5.0

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


def _is_wired_to_registry_push(workflow_path: Path) -> bool:
    try:
        data = yaml.safe_load(workflow_path.read_text())
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if isinstance(uses, str) and uses.startswith("docker/build-push-action"):
                with_block = step.get("with")
                if isinstance(with_block, dict) and with_block.get("push") is True:
                    return True
            run = step.get("run")
            if isinstance(run, str) and "docker push" in run:
                return True
    return False
