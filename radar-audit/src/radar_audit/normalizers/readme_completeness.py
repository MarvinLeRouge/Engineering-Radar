"""Normalizer scoring README completeness against standard section keywords."""

from __future__ import annotations

import re
from pathlib import Path

from radar_core.db import persisted_id
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict
from radar_core.finding_fingerprint import compute_fingerprint
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import (
    add_finding_with_recommendation,
    get_repository_path,
    save_criterion_score,
)

_README_FILENAME = "readme.md"
# Provisional banding, not yet calibrated against the real portfolio.
# "overview" alone is deliberately not a standalone match for this group: a
# generic "## Overview" header (product overview, not architecture) would
# otherwise be credited as architecture documentation.
# Each keyword is a group of terms that must all appear in the header (or link line).
# "quick start" credits both setup and usage: it is the usual home of both.
_SECTION_KEYWORDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "setup": (
        ("setup",),
        ("install",),
        ("getting started",),
        ("quick start",),
        ("quickstart",),
        ("prerequisites",),
    ),
    "usage": (
        ("usage",),
        ("how to use",),
        ("getting started",),
        ("quick start",),
        ("quickstart",),
        ("launch",),
        ("examples",),
        # "running" alone would credit "Running tests"; running the app locally is usage.
        ("running", "locally"),
        ("run", "locally"),
    ),
    "architecture overview": (("architecture",), ("how it works",), ("project structure",)),
}
_CODE_FENCE = ("```", "~~~")
# A markdown link to a local markdown file: [text](path/to/doc.md) or (doc.md#anchor).
_LOCAL_DOC_LINK = re.compile(r"\[[^\]]*\]\((?P<target>[^)\s#]+\.md)(?:#[^)]*)?\)", re.IGNORECASE)
_NO_SECTION_VALUE = 4.0
_PARTIAL_SECTION_VALUE = 7.0
_ALL_SECTIONS_VALUE = 10.0
_MISSING_README_VALUE = 0.0


def normalize_readme_completeness(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    """Score README completeness by the standard sections it documents."""
    target_path = get_repository_path(session, scoring_run)
    readme_path = _find_readme(target_path)

    if readme_path is None:
        value = _MISSING_README_VALUE
        _add_finding(
            session,
            scoring_run,
            criterion,
            "no README found",
            "Add a README.md documenting setup, usage, and an architecture overview.",
        )
    else:
        found = _matched_sections(readme_path)
        if not found:
            value = _NO_SECTION_VALUE
        elif len(found) == len(_SECTION_KEYWORDS):
            value = _ALL_SECTIONS_VALUE
        else:
            value = _PARTIAL_SECTION_VALUE
        missing = [name for name in _SECTION_KEYWORDS if name not in found]
        if missing:
            _add_finding(
                session,
                scoring_run,
                criterion,
                f"README is missing standard section(s): {', '.join(missing)}",
                f"Add a section covering {', '.join(missing)} to the README.",
            )

    return save_criterion_score(session, scoring_run, criterion, value, Confidence.MEDIUM)


def _find_readme(target_path: Path) -> Path | None:
    if not target_path.is_dir():
        return None
    for entry in target_path.iterdir():
        if entry.is_file() and entry.name.lower() == _README_FILENAME:
            return entry
    return None


def _matched_sections(readme_path: Path) -> set[str]:
    """Sections named by a header, or by a line linking to an existing local doc.

    Lines inside fenced code blocks are skipped: a shell comment is not a header.
    """
    try:
        text = readme_path.read_text()
    except OSError, UnicodeDecodeError:
        return set()

    found: set[str] = set()
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_CODE_FENCE):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("#"):
            found |= _sections_named_in(stripped.lstrip("#"))
        elif _links_to_local_doc(stripped, readme_path.parent):
            found |= _sections_named_in(stripped)
    return found


def _sections_named_in(text: str) -> set[str]:
    lowered = text.lower()
    return {
        section_name
        for section_name, keywords in _SECTION_KEYWORDS.items()
        if any(all(term in lowered for term in keyword) for keyword in keywords)
    }


def _links_to_local_doc(line: str, readme_dir: Path) -> bool:
    """Whether the line links to a markdown file that exists in the repository."""
    for match in _LOCAL_DOC_LINK.finditer(line):
        target = match.group("target")
        if "://" in target:
            continue
        if (readme_dir / target).is_file():
            return True
    return False


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    description: str,
    recommendation_text: str,
) -> None:
    add_finding_with_recommendation(
        session,
        Finding(
            scoring_run_id=persisted_id(scoring_run),
            criterion_id=persisted_id(criterion),
            severity=FindingSeverity.LOW,
            description=description,
            fingerprint=compute_fingerprint(criterion.id, FindingSeverity.LOW, None, description),
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        ),
        recommendation_text,
    )
