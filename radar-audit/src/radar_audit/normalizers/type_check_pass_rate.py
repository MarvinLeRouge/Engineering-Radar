"""Normalizer scoring type-check pass rate from mypy, tsc and phpstan results."""

from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_tool_finding, is_dismissed, score_pass_rate

_RELEVANT_TOOLS = {"mypy", "tsc", "phpstan"}
_USABLE_EXIT_CODES = {0, 1}
_SOURCE_EXTENSIONS_BY_TOOL = {"mypy": "total_files", "tsc": "total_files"}
_RECOMMENDATION_TEXT = "Fix this type error, or add a targeted suppression with justification."


def normalize_type_check_pass_rate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score type-check pass rate from mypy, tsc and phpstan results across covered files."""
    relevant = [
        r
        for r in tool_results
        if r.tool_name in _RELEVANT_TOOLS and r.exit_code in _USABLE_EXIT_CODES
    ]
    return score_pass_rate(session, scoring_run, criterion, relevant, _score_files)


def _score_files(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    if tool_result.tool_name == "phpstan":
        return _score_phpstan(session, scoring_run, criterion, tool_result)
    return _score_diagnostics_tool(session, scoring_run, criterion, tool_result)


def _score_diagnostics_tool(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    applicable = tool_result.raw_output.get("total_files", 0)
    diagnostics = tool_result.raw_output.get("diagnostics", [])
    # Blacklist "note" rather than whitelist "error": mypy diagnostics carry
    # a "severity" key ("error"/"note"/"warning"), but tsc diagnostics
    # (typescript_runner.py's regex parser) never populate that key at all
    # since every line it captures is already a real error. Whitelisting
    # "error" would silently zero out every tsc diagnostic instead.
    flagged_files = set()
    for diagnostic in diagnostics:
        finding = _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            f"{diagnostic.get('code', 'type-error')}: {diagnostic['message']}",
            file=diagnostic["file"],
            line=diagnostic.get("line"),
        )
        if diagnostic.get("severity") != "note" and not is_dismissed(session, finding):
            flagged_files.add(diagnostic["file"])
    return applicable - len(flagged_files), applicable


def _score_phpstan(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    files_with_errors = tool_result.raw_output.get("files", {})
    total_errors = tool_result.raw_output.get("totals", {}).get("file_errors", 0)
    live_files = set()
    for file_path, entry in files_with_errors.items():
        messages = entry.get("messages", [])
        if not messages:
            live_files.add(file_path)
        for message in messages:
            finding = _add_finding(
                session,
                scoring_run,
                criterion,
                tool_result,
                message["message"],
                file=file_path,
                line=message.get("line"),
            )
            if not is_dismissed(session, finding):
                live_files.add(file_path)
    # PHPStan's JSON only lists files WITH errors; the clean-file count isn't
    # directly available, so treat "no errors" as the applicable=covered=1 signal
    # and each errored file as one uncovered unit against the same denominator.
    if total_errors == 0:
        return 1, 1
    if not files_with_errors:
        return 0, 1
    return len(files_with_errors) - len(live_files), len(files_with_errors)


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    description: str,
    file: str | None = None,
    line: int | None = None,
) -> Finding:
    return add_tool_finding(
        session,
        scoring_run,
        criterion,
        tool_result,
        severity=FindingSeverity.MEDIUM,
        description=description,
        recommendation_text=_RECOMMENDATION_TEXT,
        confidence=Confidence.HIGH,
        file=file,
        line=line,
    )
