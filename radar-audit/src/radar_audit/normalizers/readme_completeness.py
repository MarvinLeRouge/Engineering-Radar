from __future__ import annotations

from pathlib import Path

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_finding_with_recommendation, get_repository_path

_README_FILENAME = "readme.md"
# Provisional banding, not yet calibrated against the real portfolio.
# "overview" alone is deliberately not a standalone match for this group: a
# generic "## Overview" header (product overview, not architecture) would
# otherwise be credited as architecture documentation.
_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "setup": ("setup", "install"),
    "usage": ("usage",),
    "architecture overview": ("architecture",),
}
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


def _find_readme(target_path: Path) -> Path | None:
    if not target_path.is_dir():
        return None
    for entry in target_path.iterdir():
        if entry.is_file() and entry.name.lower() == _README_FILENAME:
            return entry
    return None


def _matched_sections(readme_path: Path) -> set[str]:
    try:
        text = readme_path.read_text()
    except (OSError, UnicodeDecodeError):
        return set()

    found: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        header = stripped.lstrip("#").strip().lower()
        for section_name, keywords in _SECTION_KEYWORDS.items():
            if section_name in found:
                continue
            if any(keyword in header for keyword in keywords):
                found.add(section_name)
    return found


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
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            severity=FindingSeverity.LOW,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        ),
        recommendation_text,
    )
