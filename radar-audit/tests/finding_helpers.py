from radar_core.models.finding import Finding, Recommendation
from sqlmodel import select


def single_repo_level_finding(db_session, criterion) -> Finding:
    """Return the one file-less Finding of a criterion, asserting it carries a Recommendation."""
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    finding = findings[0]
    assert finding.file is None
    recommendations = db_session.exec(
        select(Recommendation).where(Recommendation.finding_id == finding.id)
    ).all()
    assert len(recommendations) == 1
    return finding


def no_findings(db_session, criterion) -> bool:
    """Tell whether a criterion has no Finding at all."""
    return not db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()


def rescore_after_dismissing(db_session, normalizer, should_dismiss):
    """Mark matching findings FALSE_POSITIVE and re-run the normalizer on the same inputs.

    Meant to follow a test that already scored the criterion once, reusing its setup.
    """
    from radar_audit.normalizers.shared import set_dismissed_fingerprints
    from radar_core.models.audit import ToolResult
    from radar_core.models.methodology import Criterion
    from radar_core.models.scoring import ScoringRun

    findings = db_session.exec(select(Finding)).all()
    assert findings
    set_dismissed_fingerprints(db_session, {f.fingerprint for f in findings if should_dismiss(f)})
    scoring_run = db_session.get(ScoringRun, findings[0].scoring_run_id)
    criterion = db_session.get(Criterion, findings[0].criterion_id)
    tool_results = list(db_session.exec(select(ToolResult)).all())
    return normalizer(db_session, scoring_run, criterion, tool_results)
