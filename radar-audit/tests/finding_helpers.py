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
