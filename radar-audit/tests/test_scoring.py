import pytest
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.normalizers.shared import add_finding_with_recommendation, get_criterion
from radar_audit.orchestrator import execute_audit
from radar_audit.scoring import (
    NoAuditFoundError,
    RepositoryNotFoundError,
    score_repository,
)
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
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


def test_score_repository_sets_global_score_as_category_weighted_average(db_session, monkeypatch):
    # Architecture & design (weight 6.15) and Security (weight 10.0) are not
    # equal, so a naive unweighted average would give a different, wrong result
    # -- this pins down the real formula, not just "some average".
    from radar_core.enums import Confidence
    from radar_core.models.audit import Audit
    from radar_core.models.repository import Repository

    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    db_session.add(Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False))
    db_session.commit()

    def _make_fake(value):
        def _fake(session, scoring_run, criterion, tool_results):
            score = Score(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                level=ScoreLevel.CRITERION,
                value=value,
                confidence=Confidence.HIGH,
            )
            session.add(score)
            session.commit()
            session.refresh(score)
            return score

        return _fake

    monkeypatch.setattr(
        "radar_audit.scoring.CRITERION_NORMALIZERS",
        {
            ("Architecture & design", "Dependency direction / circularity"): _make_fake(4.0),
            ("Security", "Dependency vulnerabilities (CVE)"): _make_fake(10.0),
        },
    )

    scoring_run = score_repository(db_session, "repo")

    expected = (6.15 * 4.0 + 10.0 * 10.0) / (6.15 + 10.0)
    assert scoring_run.global_score == pytest.approx(expected)


def test_score_repository_leaves_global_score_none_when_nothing_scored(db_session, monkeypatch):
    from radar_core.models.audit import Audit
    from radar_core.models.repository import Repository

    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    db_session.add(Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False))
    db_session.commit()

    monkeypatch.setattr("radar_audit.scoring.CRITERION_NORMALIZERS", {})

    scoring_run = score_repository(db_session, "repo")

    assert scoring_run.global_score is None
    assert scoring_run.global_confidence is None


def _fake_fingerprinted_finding(fingerprint, description="stub finding"):
    def _fake(session, scoring_run, criterion, tool_results):
        add_finding_with_recommendation(
            session,
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=None,
                severity=FindingSeverity.LOW,
                description=description,
                fingerprint=fingerprint,
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            ),
            "stub recommendation",
        )
        score = Score(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=5.0,
            confidence=Confidence.HIGH,
        )
        session.add(score)
        session.commit()
        session.refresh(score)
        return score

    return _fake


def test_human_verdict_survives_a_second_scoring_run_via_fingerprint(
    db_session, tmp_path, monkeypatch
):
    _audited_repo(db_session, tmp_path)
    fingerprint = "stub-fingerprint-aaaa"
    monkeypatch_target = "radar_audit.scoring.CRITERION_NORMALIZERS"

    monkeypatch.setattr(
        monkeypatch_target,
        {
            ("Maintainability", "Complexity hotspots"): _fake_fingerprinted_finding(fingerprint),
        },
    )

    first_run = score_repository(db_session, "repo")
    first_finding = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == first_run.id)
    ).one()
    first_finding.status = FindingStatus.RESOLVED
    first_finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    db_session.add(first_finding)
    db_session.commit()

    second_run = score_repository(db_session, "repo")
    second_finding = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == second_run.id)
    ).one()

    assert second_finding.detected_at != first_finding.detected_at
    assert second_finding.fingerprint == fingerprint
    assert second_finding.status == FindingStatus.RESOLVED
    assert second_finding.human_verdict == HumanVerdict.FALSE_POSITIVE


def test_human_verdict_does_not_leak_onto_an_unrelated_fingerprint(
    db_session, tmp_path, monkeypatch
):
    _audited_repo(db_session, tmp_path)
    monkeypatch_target = "radar_audit.scoring.CRITERION_NORMALIZERS"

    monkeypatch.setattr(
        monkeypatch_target,
        {
            ("Maintainability", "Complexity hotspots"): _fake_fingerprinted_finding(
                "fingerprint-one"
            ),
        },
    )
    first_run = score_repository(db_session, "repo")
    first_finding = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == first_run.id)
    ).one()
    first_finding.status = FindingStatus.RESOLVED
    first_finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    db_session.add(first_finding)
    db_session.commit()

    monkeypatch.setattr(
        monkeypatch_target,
        {
            ("Maintainability", "Complexity hotspots"): _fake_fingerprinted_finding(
                "fingerprint-two"
            ),
        },
    )
    second_run = score_repository(db_session, "repo")
    second_finding = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == second_run.id)
    ).one()

    assert second_finding.fingerprint == "fingerprint-two"
    assert second_finding.status == FindingStatus.OPEN
    assert second_finding.human_verdict == HumanVerdict.UNREVIEWED


def test_human_verdict_survives_a_real_re_audit_on_a_new_commit(db_session, tmp_path, monkeypatch):
    import subprocess

    fingerprint = "stub-fingerprint-cross-audit"
    monkeypatch.setattr(
        "radar_audit.scoring.CRITERION_NORMALIZERS",
        {("Maintainability", "Complexity hotspots"): _fake_fingerprinted_finding(fingerprint)},
    )

    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"a.txt": "one"})
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    first_run = score_repository(db_session, "repo")
    first_finding = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == first_run.id)
    ).one()
    first_finding.status = FindingStatus.RESOLVED
    first_finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    db_session.add(first_finding)
    db_session.commit()

    (repo_path / "a.txt").write_text("two")
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second commit"], cwd=repo_path, check=True)
    execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    second_run = score_repository(db_session, "repo")
    second_finding = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == second_run.id)
    ).one()

    assert second_run.id != first_run.id
    assert second_finding.fingerprint == fingerprint
    assert second_finding.status == FindingStatus.RESOLVED
    assert second_finding.human_verdict == HumanVerdict.FALSE_POSITIVE


def test_score_repository_promotes_findings_into_an_improvement_task(
    db_session, tmp_path, monkeypatch
):
    from radar_core.models.roadmap import ImprovementTask

    _audited_repo(db_session, tmp_path)
    monkeypatch.setattr(
        "radar_audit.scoring.CRITERION_NORMALIZERS",
        {
            ("Maintainability", "Complexity hotspots"): _fake_fingerprinted_finding(
                "promotion-test-fingerprint"
            ),
        },
    )

    score_repository(db_session, "repo")

    tasks = db_session.exec(select(ImprovementTask)).all()
    assert len(tasks) == 1


def test_every_sub_ten_scored_criterion_is_explained_by_a_finding(db_session, tmp_path):
    from radar_core.models.finding import Recommendation

    _audited_repo(
        db_session,
        tmp_path,
        files={
            "pyproject.toml": "[project]\nname='x'\ndependencies = ['sentry-sdk']\n",
            "x/__init__.py": "",
            "x/core.py": "def f():\n    return 1\n",
            "tests/test_core.py": "def test_f():\n    assert True\n",
            "tests/integration/test_flow.py": "def test_flow():\n    assert True\n",
            "docker-compose.yml": "services:\n  app:\n    image: app\n",
            "docker-compose.prod.yml": "services:\n  app:\n    image: app\n",
            ".github/workflows/deploy.yml": "name: d\non: [push]\njobs: {}\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")

    scores = db_session.exec(
        select(Score).where(
            Score.scoring_run_id == scoring_run.id,
            Score.level == ScoreLevel.CRITERION,
            Score.value < 10.0,
            Score.na_reason.is_(None),
        )
    ).all()
    assert scores
    unexplained = []
    for score in scores:
        findings = db_session.exec(
            select(Finding).where(
                Finding.scoring_run_id == scoring_run.id,
                Finding.criterion_id == score.criterion_id,
            )
        ).all()
        has_recommendation = any(
            db_session.exec(select(Recommendation).where(Recommendation.finding_id == f.id)).first()
            for f in findings
        )
        if not has_recommendation:
            unexplained.append(db_session.get(Criterion, score.criterion_id).name)
    assert unexplained == []


def test_false_positive_verdict_is_known_to_normalizers_on_the_next_score(
    db_session, tmp_path, monkeypatch
):
    from radar_audit.normalizers.shared import is_dismissed
    from radar_core.enums import HumanVerdict

    _audited_repo(db_session, tmp_path, files={"x.py": "x = 1\n"})
    first_run = score_repository(db_session, "repo")
    finding = db_session.exec(select(Finding).where(Finding.scoring_run_id == first_run.id)).first()
    assert finding is not None
    finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    db_session.add(finding)
    db_session.commit()
    fingerprint = finding.fingerprint

    second_run = score_repository(db_session, "repo")

    rescored = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == second_run.id, Finding.fingerprint == fingerprint
        )
    ).one()
    assert rescored.human_verdict == HumanVerdict.FALSE_POSITIVE
    seen = []
    monkeypatch.setattr(
        "radar_audit.scoring._score_run",
        lambda session, *args: seen.append(is_dismissed(session, rescored)) or second_run,
    )
    score_repository(db_session, "repo")
    assert seen == [True]


def _new_commit_and_score(db_session, tmp_path, marker):
    import subprocess

    repo_path = tmp_path / "repo"
    (repo_path / f"{marker}.txt").write_text(marker)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-qm", marker], cwd=repo_path, check=True)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)
    return score_repository(db_session, "repo")


def test_reverting_a_carried_false_positive_sticks_on_the_next_audit(db_session, tmp_path):
    from radar_audit.normalizers.shared import is_dismissed, set_dismissed_fingerprints
    from radar_core.enums import HumanVerdict

    _audited_repo(db_session, tmp_path, files={"x.py": "x = 1\n"})
    run_a = score_repository(db_session, "repo")
    finding = db_session.exec(select(Finding).where(Finding.scoring_run_id == run_a.id)).first()
    assert finding is not None
    fingerprint = finding.fingerprint
    finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    db_session.add(finding)
    db_session.commit()

    run_b = _new_commit_and_score(db_session, tmp_path, "b")
    carried = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == run_b.id, Finding.fingerprint == fingerprint
        )
    ).one()
    assert carried.human_verdict == HumanVerdict.FALSE_POSITIVE
    carried.human_verdict = HumanVerdict.UNREVIEWED
    db_session.add(carried)
    db_session.commit()

    run_c = _new_commit_and_score(db_session, tmp_path, "c")

    latest = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == run_c.id, Finding.fingerprint == fingerprint
        )
    ).one()
    assert latest.human_verdict == HumanVerdict.UNREVIEWED
    from radar_audit.scoring import _collect_carried_verdicts
    from radar_core.models.repository import Repository

    repository = db_session.exec(select(Repository).where(Repository.name == "repo")).one()
    set_dismissed_fingerprints(
        db_session,
        {
            fp
            for fp, (_, verdict, _) in _collect_carried_verdicts(db_session, repository).items()
            if verdict == HumanVerdict.FALSE_POSITIVE
        },
    )
    assert not is_dismissed(db_session, latest)


def test_dismissed_fingerprints_are_cleared_after_scoring(db_session, tmp_path):
    from radar_audit.normalizers.shared import is_dismissed
    from radar_core.enums import HumanVerdict

    _audited_repo(db_session, tmp_path, files={"x.py": "x = 1\n"})
    run = score_repository(db_session, "repo")
    finding = db_session.exec(select(Finding).where(Finding.scoring_run_id == run.id)).first()
    assert finding is not None
    finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    db_session.add(finding)
    db_session.commit()
    fingerprint = finding.fingerprint

    run = score_repository(db_session, "repo")

    rescored = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == run.id, Finding.fingerprint == fingerprint)
    ).one()
    assert not is_dismissed(db_session, rescored)


def _add_trivy_image_result(db_session, audit_id, subproject_path):
    from radar_core.models.audit import ToolResult

    db_session.add(
        ToolResult(
            audit_id=audit_id,
            subproject_path=subproject_path,
            tool_name="trivy-image",
            tool_version="1.0.0",
            command="stub",
            raw_output={
                "image_found": True,
                "vulnerabilities": [{"id": "CVE-2024-1", "severity": "HIGH", "pkg": "openssl"}],
            },
            exit_code=0,
            duration_ms=1,
        )
    )
    db_session.commit()


def test_verdict_set_before_findings_carried_their_image_still_applies_per_image(
    db_session, tmp_path
):
    import subprocess

    from radar_core.finding_fingerprint import compute_fingerprint

    audit = _audited_repo(db_session, tmp_path)
    _add_trivy_image_result(db_session, audit.id, "radar-api")
    run_a = score_repository(db_session, "repo")
    old = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == run_a.id, Finding.description == "CVE-2024-1: openssl"
        )
    ).one()
    # Recreate a row as scored before FIX-025: no file, fingerprint without the image.
    old.file = None
    old.fingerprint = compute_fingerprint(old.criterion_id, old.severity, None, old.description)
    old.status = FindingStatus.WONT_FIX
    old.human_verdict = HumanVerdict.TRUE_POSITIVE
    db_session.add(old)
    db_session.commit()

    repo_path = tmp_path / "repo"
    (repo_path / "b.txt").write_text("b")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-qm", "b"], cwd=repo_path, check=True)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    new_audit = execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)
    _add_trivy_image_result(db_session, new_audit.id, "radar-api")
    _add_trivy_image_result(db_session, new_audit.id, "radar-audit")
    run_b = score_repository(db_session, "repo")

    carried = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == run_b.id, Finding.description == "CVE-2024-1: openssl"
        )
    ).all()
    by_image = {f.file: (f.status, f.human_verdict) for f in carried}
    assert by_image["radar-api"] == (FindingStatus.WONT_FIX, HumanVerdict.TRUE_POSITIVE)
    # The image first scanned after FIX-025 gets no verdict from another image.
    assert by_image["radar-audit"] == (FindingStatus.OPEN, HumanVerdict.UNREVIEWED)


def test_score_repository_logs_the_result_with_the_audit_id(db_session, tmp_path):
    import structlog
    from structlog.testing import capture_logs

    audit = _audited_repo(db_session, tmp_path)

    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
        scoring_run = score_repository(db_session, "repo")

    [entry] = [log for log in logs if log["event"] == "scoring_finished"]
    assert entry["repo"] == "repo"
    assert entry["audit_id"] == audit.id
    assert entry["global_score"] == scoring_run.global_score
    assert isinstance(entry["findings"], int)


def test_verdict_note_is_carried_to_a_new_audit_and_dropped_when_the_verdict_is_reverted(
    db_session, tmp_path
):
    from radar_core.enums import HumanVerdict

    _audited_repo(db_session, tmp_path, files={"x.py": "x = 1\n"})
    run_a = score_repository(db_session, "repo")
    finding = db_session.exec(select(Finding).where(Finding.scoring_run_id == run_a.id)).first()
    assert finding is not None
    fingerprint = finding.fingerprint
    finding.human_verdict = HumanVerdict.FALSE_POSITIVE
    finding.verdict_note = "Framework convention, used at runtime"
    db_session.add(finding)
    db_session.commit()

    run_b = _new_commit_and_score(db_session, tmp_path, "b")
    carried = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == run_b.id, Finding.fingerprint == fingerprint
        )
    ).one()
    assert carried.verdict_note == "Framework convention, used at runtime"
    carried.human_verdict = HumanVerdict.UNREVIEWED
    db_session.add(carried)
    db_session.commit()

    run_c = _new_commit_and_score(db_session, tmp_path, "c")
    latest = db_session.exec(
        select(Finding).where(
            Finding.scoring_run_id == run_c.id, Finding.fingerprint == fingerprint
        )
    ).one()
    assert latest.verdict_note is None
