"""Grouping of scoring findings into improvement tasks and roadmap items."""

from __future__ import annotations

import re

from radar_core.enums import FindingSeverity, RoadmapStatus
from radar_core.improvement_task_grouping import compute_task_group_key
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Criterion
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select

# These two criteria's own Finding data already spans multiple files in one
# row (a dependency cycle lists every module involved; a duplication finding
# references both sides of the pair) and the fix is already localized to one
# place -- grouping them further by (criterion, file) would wrongly merge
# unrelated cycles/duplicate pairs that happen to share a file. See
# project_roadmap_roi_design memory / docs/roadmap.md Section 7.
_ATOMIC_CRITERION_NAMES = frozenset({"Dependency direction / circularity", "Code duplication"})

_SEVERITY_CRITICALITY: dict[FindingSeverity, float] = {
    FindingSeverity.CRITICAL: 4.0,
    FindingSeverity.HIGH: 3.0,
    FindingSeverity.MEDIUM: 2.0,
    FindingSeverity.LOW: 1.0,
    FindingSeverity.INFO: 0.0,
}
_PRIORITY_DECIMALS = 1
# Matches code_duplication.py's own description format exactly:
# f"Duplicated block between {first['name']}:{first['start']}-{first['end']} "
# f"and {second['name']}:{second['start']}-{second['end']}"
_DUPLICATION_FILES_PATTERN = re.compile(r"Duplicated block between (\S+):\d+-\d+ and (\S+):\d+-\d+")


def promote_improvement_tasks(session: Session, scoring_run: ScoringRun) -> None:
    """Group this scoring run's Findings into ImprovementTask/RoadmapItem rows.

    Upserts by a stable group key (radar_core.improvement_task_grouping) so a
    human-set RoadmapItem.status/estimated_effort/estimated_impact/done_at
    survives a re-audit, the same way Finding.fingerprint already does since
    FEAT-022 -- only membership (which findings are linked) and the derived
    priority get refreshed on every call.

    Deliberately does not filter by Finding.status/human_verdict: excluding a
    dismissed finding from promotion is the separate, not-yet-built on-demand
    recalculation feature (docs/roadmap.md Section 8), out of scope here.
    """
    findings = list(session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)))
    if not findings:
        return

    recommendation_by_finding = _build_recommendation_lookup(session, findings)
    groups, group_criterion_and_file = _group_findings_by_task(session, findings)

    for group_key, group_findings in groups.items():
        criterion_id, file = group_criterion_and_file[group_key]
        criterion = session.get(Criterion, criterion_id)
        assert criterion is not None
        _upsert_task(session, group_key, criterion, file, group_findings, recommendation_by_finding)


def _build_recommendation_lookup(session: Session, findings: list[Finding]) -> dict[int, str]:
    return {
        r.finding_id: r.text
        for r in session.exec(
            select(Recommendation).where(
                Recommendation.finding_id.in_(  # type: ignore[attr-defined]
                    [f.id for f in findings if f.id is not None]
                )
            )
        )
    }


def _group_findings_by_task(
    session: Session, findings: list[Finding]
) -> tuple[dict[str, list[Finding]], dict[str, tuple[int, str | None]]]:
    groups: dict[str, list[Finding]] = {}
    group_criterion_and_file: dict[str, tuple[int, str | None]] = {}
    for finding in findings:
        if finding.fingerprint is None:
            # No stable identity to upsert against -- skip rather than create
            # a task that would duplicate on every single re-score.
            continue
        criterion = session.get(Criterion, finding.criterion_id)
        assert criterion is not None
        group_key = _compute_group_key(finding, criterion)
        groups.setdefault(group_key, []).append(finding)
        group_criterion_and_file[group_key] = (finding.criterion_id, finding.file)
    return groups, group_criterion_and_file


def _compute_group_key(finding: Finding, criterion: Criterion) -> str:
    atomic = finding.file is None or criterion.name in _ATOMIC_CRITERION_NAMES
    if atomic:
        return compute_task_group_key(
            finding.criterion_id, finding.file, atomic_finding_fingerprint=finding.fingerprint
        )
    return compute_task_group_key(finding.criterion_id, finding.file)


def _upsert_task(
    session: Session,
    group_key: str,
    criterion: Criterion,
    file: str | None,
    findings: list[Finding],
    recommendation_by_finding: dict[int, str],
) -> None:
    task = session.exec(
        select(ImprovementTask).where(ImprovementTask.group_key == group_key)
    ).first()
    title = f"{criterion.name}: {file}" if file else criterion.name
    description = _build_description(findings, recommendation_by_finding)

    if task is None:
        task = ImprovementTask(
            title=title,
            description=description,
            criterion_id=criterion.id,
            file=file,
            group_key=group_key,
        )
    else:
        task.title = title
        task.description = description
    session.add(task)
    # Flush (not commit) to get task.id assigned without ending the
    # transaction -- the whole upsert commits once at the end, so a failure
    # partway through never leaves a task durably committed without its
    # links/roadmap item.
    session.flush()

    assert task.id is not None
    for existing_link in session.exec(
        select(FindingImprovementTaskLink).where(
            FindingImprovementTaskLink.improvement_task_id == task.id
        )
    ):
        session.delete(existing_link)
    session.flush()
    for finding in findings:
        assert finding.id is not None
        session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))

    priority = _compute_priority(criterion, file, findings)
    roadmap_item = session.exec(
        select(RoadmapItem).where(RoadmapItem.improvement_task_id == task.id)
    ).first()
    if roadmap_item is None:
        roadmap_item = RoadmapItem(
            improvement_task_id=task.id, status=RoadmapStatus.TODO, priority=priority
        )
    else:
        roadmap_item.priority = priority
    session.add(roadmap_item)
    session.commit()


def _build_description(findings: list[Finding], recommendation_by_finding: dict[int, str]) -> str:
    recommendation_texts = {
        recommendation_by_finding[f.id] for f in findings if f.id in recommendation_by_finding
    }
    lines = sorted(recommendation_texts)
    lines.extend(f"- {f.description}" for f in findings)
    return "\n".join(lines)


def _compute_priority(criterion: Criterion, file: str | None, findings: list[Finding]) -> float:
    worst = max(_SEVERITY_CRITICALITY.get(f.severity, 0.0) for f in findings)
    files_impacted, files_to_fix = _files_ratio(criterion, file, findings)
    return round(worst * files_impacted / files_to_fix, _PRIORITY_DECIMALS)


def _files_ratio(
    criterion: Criterion, file: str | None, findings: list[Finding]
) -> tuple[int, int]:
    if criterion.name not in _ATOMIC_CRITERION_NAMES or file is None:
        return 1, 1
    # 1.1/2.5 atomic case: files_impacted is the count of distinct files
    # referenced across the group's own finding description(s); files_to_fix
    # is always 1 (breaking a cycle, or extracting a duplicate, is one
    # localized fix). Usually one finding per atomic group, but a fingerprint
    # collision (e.g. the same duplicated fragment appearing between the same
    # file pair more than once, see FEAT-022) can legitimately merge several
    # findings into one group -- summed across all of them, not just the first.
    if criterion.name == "Code duplication":
        return _duplication_files_impacted(findings), 1
    # "Circular dependency involving: a, b, c" -- comma-separated module list.
    involved = findings[0].description.split(":", 1)[-1]
    files_impacted = len([m for m in involved.split(",") if m.strip()])
    return max(files_impacted, 1), 1


def _duplication_files_impacted(findings: list[Finding]) -> int:
    files: set[str] = set()
    for finding in findings:
        match = _DUPLICATION_FILES_PATTERN.search(finding.description)
        if match:
            files.update(match.groups())
        elif finding.file:
            # Description format changed unexpectedly -- fall back to the
            # one file we do know about rather than silently losing it.
            files.add(finding.file)
    return max(len(files), 1)
