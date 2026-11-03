"""Weighted risk of a scoring run, shared by the score history and the report."""

from __future__ import annotations

from radar_core.enums import SEVERITY_RISK_WEIGHT, FindingSeverity, FindingStatus, HumanVerdict
from radar_core.models.finding import Finding
from radar_core.models.scoring import ScoringRun
from sqlalchemy import func
from sqlmodel import Session, select

from radar_api.schemas.history import SeverityRiskPoint

_RISK_SEVERITIES = [s for s in FindingSeverity if SEVERITY_RISK_WEIGHT[s] > 0]


def compute_risk(session: Session, scoring_run: ScoringRun) -> list[SeverityRiskPoint]:
    """Weighted risk per severity of one scoring run: OPEN, non-FALSE_POSITIVE findings count."""
    rows = session.exec(
        select(Finding.severity, Finding.status, Finding.human_verdict, func.count())
        .where(Finding.scoring_run_id == scoring_run.id)
        .group_by(Finding.severity, Finding.status, Finding.human_verdict)
    ).all()
    counted: dict[FindingSeverity, int] = {}
    excluded: dict[FindingSeverity, int] = {}
    for severity, status, verdict, total in rows:
        is_counted = status == FindingStatus.OPEN and verdict != HumanVerdict.FALSE_POSITIVE
        target = counted if is_counted else excluded
        key = FindingSeverity(severity)
        target[key] = target.get(key, 0) + total

    return [
        SeverityRiskPoint(
            severity=severity.value,
            weight=SEVERITY_RISK_WEIGHT[severity],
            count=counted.get(severity, 0),
            excluded=excluded.get(severity, 0),
            weighted=counted.get(severity, 0) * SEVERITY_RISK_WEIGHT[severity],
        )
        for severity in _RISK_SEVERITIES
    ]
