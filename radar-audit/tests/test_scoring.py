import pytest
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.normalizers.shared import get_criterion
from radar_audit.orchestrator import execute_audit
from radar_audit.scoring import (
    NoAuditFoundError,
    RepositoryNotFoundError,
    score_repository,
)
from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score
from sqlmodel import select

from tests.git_helpers import init_git_repo


def _audited_repo(db_session, tmp_path, name="repo", files=None):
    repo_path = tmp_path / name
    init_git_repo(repo_path, files=files or {})
    config = PortfolioConfig(repos_root=tmp_path, repositories=[name])
    return execute_audit(db_session, config, name, DEFAULT_RUNNERS)


def test_score_repository_raises_when_repository_unknown(db_session):
    with pytest.raises(RepositoryNotFoundError, match="does-not-exist"):
        score_repository(db_session, "does-not-exist")


def test_score_repository_raises_when_no_audit_exists(db_session):
    from radar_core.models.repository import Repository

    db_session.add(Repository(name="unaudited", path="/tmp/unaudited"))
    db_session.commit()

    with pytest.raises(NoAuditFoundError, match="unaudited"):
        score_repository(db_session, "unaudited")


def test_score_repository_creates_criterion_and_category_scores(db_session, tmp_path):
    _audited_repo(
        db_session,
        tmp_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    criterion_scores = [s for s in scores if s.level == ScoreLevel.CRITERION]
    category_scores = [s for s in scores if s.level == ScoreLevel.CATEGORY]

    assert len(criterion_scores) >= 1
    assert len(category_scores) >= 1
    assert all(0.0 <= s.value <= 10.0 for s in category_scores)


def test_score_repository_is_idempotent_no_duplicate_scores(db_session, tmp_path):
    _audited_repo(
        db_session,
        tmp_path,
        files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"},
    )

    first_run = score_repository(db_session, "repo")
    first_count = len(
        db_session.exec(select(Score).where(Score.scoring_run_id == first_run.id)).all()
    )

    second_run = score_repository(db_session, "repo")
    second_count = len(
        db_session.exec(select(Score).where(Score.scoring_run_id == second_run.id)).all()
    )

    assert first_run.id == second_run.id
    assert first_count == second_count


def test_score_repository_is_idempotent_no_duplicate_findings(db_session, tmp_path):
    # No DESIGN.md, so the design-doc-presence normalizer creates a Finding ("no
    # architectural documentation found") on every call to score_repository. Without
    # deleting the previous pass's Finding rows first, a second call would duplicate
    # every Finding, same failure mode as the Score duplication this idempotency test
    # sits next to.
    _audited_repo(db_session, tmp_path)

    first_run = score_repository(db_session, "repo")
    first_finding_count = len(
        db_session.exec(select(Finding).where(Finding.scoring_run_id == first_run.id)).all()
    )
    assert first_finding_count >= 1

    second_run = score_repository(db_session, "repo")
    second_finding_count = len(
        db_session.exec(select(Finding).where(Finding.scoring_run_id == second_run.id)).all()
    )

    assert first_run.id == second_run.id
    assert first_finding_count == second_finding_count


def test_score_repository_refreshes_scored_at_when_reusing_scoring_run(db_session, tmp_path):
    _audited_repo(db_session, tmp_path)

    first_run = score_repository(db_session, "repo")
    first_scored_at = first_run.scored_at

    second_run = score_repository(db_session, "repo")

    assert first_run.id == second_run.id
    assert second_run.scored_at >= first_scored_at


def test_category_score_redistributes_weight_over_scored_criteria_only(db_session, tmp_path):
    # Architecture & design has 4 criteria at weight 25.0 each, but only 3 are
    # ever scored (1.4 has no normalizer). Equal weights mean the redistributed
    # weighted average reduces to a plain average of exactly those 3 -- not a
    # naive /4 average that would silently treat the missing one as a zero.
    _audited_repo(
        db_session,
        tmp_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")
    methodology_version_id = scoring_run.methodology_version_id
    arch_criterion = get_criterion(
        db_session,
        methodology_version_id,
        "Architecture & design",
        "Dependency direction / circularity",
    )
    arch_criterion_ids = {
        c.id
        for c in db_session.exec(
            select(Criterion).where(Criterion.category_id == arch_criterion.category_id)
        ).all()
    }

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    arch_criterion_scores = [
        s
        for s in scores
        if s.level == ScoreLevel.CRITERION and s.criterion_id in arch_criterion_ids
    ]
    arch_category_score = next(
        s
        for s in scores
        if s.level == ScoreLevel.CATEGORY and s.category_id == arch_criterion.category_id
    )

    assert len(arch_criterion_scores) == 3
    expected = sum(s.value for s in arch_criterion_scores) / len(arch_criterion_scores)
    assert arch_category_score.value == pytest.approx(expected)


def test_category_score_excludes_na_reason_scores_from_weighted_average(db_session, monkeypatch):
    # A Score carrying na_reason (e.g. a permanent not-applicable case) must stay
    # persisted but must not drag the category's weighted average toward its
    # placeholder value -- otherwise N/A and "genuinely scored low" would look
    # identical at the category level.
    from radar_core.models.audit import Audit
    from radar_core.models.repository import Repository

    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()

    def _fake_scored(session, scoring_run, criterion, tool_results):
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=8.0,
            confidence=Confidence.HIGH,
        )
        session.add(score)
        session.commit()
        session.refresh(score)
        return score

    def _fake_na(session, scoring_run, criterion, tool_results):
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=0.0,
            confidence=Confidence.HIGH,
            na_reason="stub reason",
        )
        session.add(score)
        session.commit()
        session.refresh(score)
        return score

    monkeypatch.setattr(
        "radar_audit.scoring.CRITERION_NORMALIZERS",
        {
            ("Maintainability", "Complexity hotspots"): _fake_scored,
            (
                "Maintainability",
                "Documentation-in-code (docstring/comment coverage)",
            ): _fake_na,
        },
    )

    scoring_run = score_repository(db_session, "repo")

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    category_score = next(s for s in scores if s.level == ScoreLevel.CATEGORY)
    na_score = next(s for s in scores if s.na_reason is not None)

    assert na_score.value == 0.0
    assert category_score.value == 8.0
