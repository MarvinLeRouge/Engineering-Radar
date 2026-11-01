"""Priority ordering for findings by severity, magnitude, file and description."""

from __future__ import annotations

from collections.abc import Sequence

from radar_core.enums import FindingSeverity
from radar_core.models.finding import Finding

_SEVERITY_RANK: dict[FindingSeverity, int] = {
    FindingSeverity.CRITICAL: 0,
    FindingSeverity.HIGH: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 3,
    FindingSeverity.INFO: 4,
}


def sort_findings_by_priority(findings: Sequence[Finding]) -> list[Finding]:
    """Sort findings by severity, then by magnitude descending when present,
    then alphabetically by file and description.

    Within the same severity, a finding with a magnitude (e.g. a cyclomatic
    complexity value) sorts before one without, so the worst offender is
    handled first. Findings that tie on severity and magnitude (including
    two findings with no magnitude at all) are ordered alphabetically by
    file then description, rather than left in arbitrary insertion order.
    """
    return sorted(findings, key=_priority_key)


def _priority_key(finding: Finding) -> tuple[int, int, float, str, str]:
    severity_rank = _SEVERITY_RANK.get(finding.severity, len(_SEVERITY_RANK))
    file_key = finding.file or ""
    description_key = finding.description
    if finding.magnitude is None:
        return (severity_rank, 1, 0.0, file_key, description_key)
    return (severity_rank, 0, -finding.magnitude, file_key, description_key)
