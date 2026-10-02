from __future__ import annotations

from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import score_design_doc_evidence


def normalize_design_doc(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    return score_design_doc_evidence(
        session,
        scoring_run,
        criterion,
        tool_results,
        missing_description="no architectural documentation found",
        missing_recommendation=(
            "Add a DESIGN.md or ARCHITECTURE.md describing the system's structure."
        ),
        trivial_description=lambda found_path, non_blank_lines: (
            f"architectural documentation at {found_path} is trivial "
            f"({non_blank_lines} non-blank lines)"
        ),
        trivial_recommendation=lambda found_path: (
            f"Expand {found_path} with more detail on the system's structure and key decisions."
        ),
    )
