"""Normalizer scoring Dockerfile hardening from hadolint findings and severities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.finding_fingerprint import compute_fingerprint
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import (
    add_finding_with_recommendation,
    get_repository_path,
    has_success_payload,
    read_source_line,
)

_RECOMMENDATION_TEXT = (
    "Apply the hadolint recommendation, for example pinning versions or using a non-root user."
)
_RAW_SEVERITY_MAP = {"error": "HIGH", "warning": "MEDIUM", "info": "LOW", "style": "LOW"}
_SEVERITY_ENUM = {
    "HIGH": FindingSeverity.HIGH,
    "MEDIUM": FindingSeverity.MEDIUM,
    "LOW": FindingSeverity.LOW,
}
# Worst-severity-present bands, same scale as sast_findings.py's (4.3) for
# cross-criterion consistency -- resolved but provisional, pending Phase 5
# portfolio-wide calibration. Hadolint has no CRITICAL-equivalent level, so
# that row is never actually reached here.
_BAND_VALUE = {"NONE": 10.0, "LOW": 6.0, "MEDIUM": 6.0, "HIGH": 4.0, "CRITICAL": 2.0}
_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _process_dockerfiles(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    repo_path: Path,
) -> tuple[int, str]:
    total = 0
    worst = "NONE"
    for entry in tool_result.raw_output["dockerfiles"]:
        findings = entry.get("findings")
        # A Dockerfile hadolint failed to lint carries an "error" key instead of a
        # findings list: it is excluded rather than counted either way.
        if not isinstance(findings, list) or "error" in entry:
            continue
        total += 1
        entry_worst = _process_dockerfile_findings(
            session, scoring_run, criterion, tool_result, repo_path, entry, findings
        )
        if _SEVERITY_RANK.get(entry_worst, 1) > _SEVERITY_RANK[worst]:
            worst = entry_worst
    return total, worst


def _process_dockerfile_findings(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    repo_path: Path,
    entry: dict[str, Any],
    findings: list[dict[str, Any]],
) -> str:
    worst = "NONE"
    for finding in findings:
        raw_severity = finding.get("level", "")
        severity = _RAW_SEVERITY_MAP.get(raw_severity, "MEDIUM")
        _add_dockerfile_finding(
            session, scoring_run, criterion, tool_result, repo_path, entry, finding, severity
        )
        if _SEVERITY_RANK.get(severity, 1) > _SEVERITY_RANK[worst]:
            worst = severity
    return worst


def _add_dockerfile_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    repo_path: Path,
    entry: dict[str, Any],
    finding: dict[str, Any],
    severity: str,
) -> None:
    resolved_severity = _SEVERITY_ENUM.get(severity, FindingSeverity.MEDIUM)
    file = entry["path"]
    line = finding.get("line")
    # Hadolint gives no per-instance identifier beyond rule code +
    # line/column -- fall back to the flagged source line's own
    # text, which survives unrelated edits elsewhere in the file.
    source_line = read_source_line(repo_path, file, line)
    label = f"{finding['code']}: {source_line or ''}"
    add_finding_with_recommendation(
        session,
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=resolved_severity,
            description=f"{finding['code']}: {finding['message']}",
            file=file,
            line=line,
            fingerprint=compute_fingerprint(criterion.id, resolved_severity, file, label),
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        ),
        _RECOMMENDATION_TEXT,
    )


def normalize_dockerfile_hardening(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score Dockerfile hardening from hadolint findings, banded by worst severity present."""
    # A crashed hadolint run carries no "dockerfiles" list and is missing data.
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "hadolint" and has_success_payload(r, "dockerfiles")
    ]
    if not relevant:
        return None

    repo_path = get_repository_path(session, scoring_run)
    total = 0
    worst = "NONE"
    for tool_result in relevant:
        entries_total, entries_worst = _process_dockerfiles(
            session, scoring_run, criterion, tool_result, repo_path
        )
        total += entries_total
        if _SEVERITY_RANK.get(entries_worst, 1) > _SEVERITY_RANK[worst]:
            worst = entries_worst

    if total == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_BAND_VALUE[worst],
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
