"""Create a fresh SQLite database with a fixed dataset for the dashboard E2E tests.

Usage: uv run --package radar-api python scripts/seed_e2e_db.py <path/to/e2e.db>
The database is deleted and recreated on every run, so tests always start from
the same state. It never touches the real radar.db.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from radar_core.db import get_engine
from radar_core.enums import (
    Confidence,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    ScoreLevel,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session, SQLModel

RADAR_CORE_ROOT = Path(__file__).resolve().parents[1] / "radar-core"


def _migrate(database_url: str) -> None:
    config = Config(str(RADAR_CORE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(RADAR_CORE_ROOT / "alembic"))
    os.environ["RADAR_DATABASE_URL"] = database_url
    command.upgrade(config, "head")


def _add[RowT: SQLModel](session: Session, row: RowT) -> RowT:
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _scoring_run(
    session: Session,
    repository: Repository,
    methodology: MethodologyVersion,
    commit_sha: str,
    scored_at: datetime,
    global_score: float,
) -> ScoringRun:
    audit = _add(
        session,
        Audit(repository_id=repository.id, commit_sha=commit_sha, audited_at=scored_at),
    )
    return _add(
        session,
        ScoringRun(
            audit_id=audit.id,
            methodology_version_id=methodology.id,
            scored_at=scored_at,
            global_score=global_score,
            global_confidence=Confidence.HIGH,
        ),
    )


def _scores(
    session: Session,
    run: ScoringRun,
    category: Category,
    criteria_values: list[tuple[Criterion, float]],
) -> None:
    for criterion, value in criteria_values:
        session.add(
            Score(
                scoring_run_id=run.id,
                criterion_id=criterion.id,
                level=ScoreLevel.CRITERION,
                value=value,
                confidence=Confidence.HIGH,
            )
        )
    category_value = sum(value for _, value in criteria_values) / len(criteria_values)
    session.add(
        Score(
            scoring_run_id=run.id,
            category_id=category.id,
            level=ScoreLevel.CATEGORY,
            value=category_value,
            confidence=Confidence.HIGH,
        )
    )
    session.commit()


def _finding(
    session: Session,
    run: ScoringRun,
    criterion: Criterion,
    severity: FindingSeverity,
    description: str,
    status: FindingStatus = FindingStatus.OPEN,
    verdict: HumanVerdict = HumanVerdict.UNREVIEWED,
) -> None:
    finding = _add(
        session,
        Finding(
            scoring_run_id=run.id,
            criterion_id=criterion.id,
            severity=severity,
            description=description,
            file="src/app.py",
            confidence=Confidence.HIGH,
            status=status,
            human_verdict=verdict,
        ),
    )
    session.add(Recommendation(finding_id=finding.id, text=f"Fix: {description}"))
    session.commit()


def seed(session: Session) -> None:
    """Insert one repository with two scoring runs and findings covering every verdict state."""
    methodology = _add(session, MethodologyVersion(version_label="e2e"))
    security = _add(
        session,
        Category(methodology_version_id=methodology.id, name="Security", weight=1.0, order=1),
    )
    vulnerabilities = _add(
        session,
        Criterion(
            category_id=security.id,
            name="Dependency vulnerabilities",
            description="Known CVEs in dependencies.",
            weight=1.0,
            scoring_model=ScoringModel.FIXED_SCALE,
            implemented=True,
        ),
    )
    secrets = _add(
        session,
        Criterion(
            category_id=security.id,
            name="Secrets in tracked history",
            description="Credentials committed to git.",
            weight=1.0,
            scoring_model=ScoringModel.FIXED_SCALE,
            implemented=True,
        ),
    )
    # A category radar-audit cannot score yet: shown greyed out in Trends and the report.
    planned = _add(
        session,
        Category(methodology_version_id=methodology.id, name="Technical debt", weight=1.0, order=2),
    )
    _add(
        session,
        Criterion(
            category_id=planned.id,
            name="TODO/FIXME density",
            description="Leftover markers per KLOC.",
            weight=1.0,
            scoring_model=ScoringModel.FIXED_SCALE,
        ),
    )
    repository = _add(session, Repository(name="demo-app", path="/repos/demo-app"))

    older = _scoring_run(
        session, repository, methodology, "a" * 40, datetime(2026, 10, 1, tzinfo=UTC), 4.0
    )
    _scores(session, older, security, [(vulnerabilities, 2.0), (secrets, 6.0)])
    _finding(session, older, vulnerabilities, FindingSeverity.CRITICAL, "CVE-2026-0001: openssl")

    latest = _scoring_run(
        session, repository, methodology, "b" * 40, datetime(2026, 11, 1, tzinfo=UTC), 6.0
    )
    _scores(session, latest, security, [(vulnerabilities, 4.0), (secrets, 8.0)])
    _finding(session, latest, vulnerabilities, FindingSeverity.HIGH, "CVE-2026-0002: libexpat")
    _finding(session, latest, vulnerabilities, FindingSeverity.HIGH, "CVE-2026-0003: zlib")
    _finding(
        session,
        latest,
        vulnerabilities,
        FindingSeverity.HIGH,
        "CVE-2026-0004: ncurses",
        status=FindingStatus.WONT_FIX,
        verdict=HumanVerdict.TRUE_POSITIVE,
    )
    _finding(
        session,
        latest,
        secrets,
        FindingSeverity.MEDIUM,
        "Possible AWS key in config/example.env",
        verdict=HumanVerdict.FALSE_POSITIVE,
    )
    _finding(session, latest, secrets, FindingSeverity.LOW, "Generic token in docs/setup.md")


def main() -> None:
    db_path = Path(sys.argv[1]).resolve()
    if db_path.suffix != ".db":
        sys.exit(f"refusing to recreate {db_path}: expected a .db file")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    database_url = f"sqlite:///{db_path}"
    _migrate(database_url)
    engine = get_engine(database_url)
    with Session(engine) as session:
        seed(session)
    engine.dispose()


if __name__ == "__main__":
    main()
