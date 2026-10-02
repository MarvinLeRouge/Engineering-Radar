from __future__ import annotations

from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import score_design_doc_evidence

# Shares evidence with criterion 1.2 (Architectural documentation present): same
# tool, same banding, reframed for documentation completeness/onboarding rather
# than structural fidelity. Cross-referenced per the Quality Framework, not
# double-weighted.


def normalize_architecture_documentation(
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
        missing_description="no architecture documentation available for onboarding",
        missing_recommendation=(
            "Add a DESIGN.md or ARCHITECTURE.md so new contributors can get oriented."
        ),
        trivial_description=lambda found_path, non_blank_lines: (
            f"architecture documentation at {found_path} is too short to onboard from "
            f"({non_blank_lines} non-blank lines)"
        ),
        trivial_recommendation=lambda found_path: (
            f"Expand {found_path} so it is usable as an onboarding reference."
        ),
    )
