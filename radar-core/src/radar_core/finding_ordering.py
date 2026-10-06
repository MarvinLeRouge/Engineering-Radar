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
    """Sort findings by severity, then by magnitude descending when present.

    Within the same severity, a finding with a magnitude (e.g. a cyclomatic
    complexity value) sorts before one without, so the worst offender is
    handled first. The sort is stable: findings with no magnitude, or with
    an equal magnitude, keep their original relative order.
    """
    return sorted(findings, key=_priority_key)


def _priority_key(finding: Finding) -> tuple[int, int, float]:
    severity_rank = _SEVERITY_RANK.get(finding.severity, len(_SEVERITY_RANK))
    if finding.magnitude is None:
        return (severity_rank, 1, 0.0)
    return (severity_rank, 0, -finding.magnitude)
