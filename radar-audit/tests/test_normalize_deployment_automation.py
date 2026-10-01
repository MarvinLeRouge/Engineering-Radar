from radar_audit.normalizers.deployment_automation import normalize_deployment_automation
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository


def _make_scoring_run_and_criterion(db_session, repo_path):
    repo = Repository(name="repo", path=str(repo_path))
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "DevOps / CI-CD", "Deployment automation"
    )
    return scoring_run, criterion


_WIRED_WORKFLOW = """\
name: Build and push
on: [push]
jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/example/app:latest
"""

_UNWIRED_WORKFLOW = """\
name: Build
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v6
        with:
          push: false
"""

_SHELL_PUSH_WORKFLOW = """\
name: Deploy
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: docker push ghcr.io/example/app:latest
"""


def test_no_workflows_directory_returns_none(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_deployment_automation(db_session, scoring_run, criterion, [])

    assert score is None


def test_no_candidate_file_scores_todo(db_session, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\non: [push]\njobs: {}\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_deployment_automation(db_session, scoring_run, criterion, [])

    assert score.value == 0.0


def test_candidate_present_but_not_wired_scores_in_progress(db_session, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "build-push.yml").write_text(_UNWIRED_WORKFLOW)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_deployment_automation(db_session, scoring_run, criterion, [])

    assert score.value == 5.0


def test_candidate_wired_to_build_push_action_scores_done(db_session, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "build-push.yml").write_text(_WIRED_WORKFLOW)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_deployment_automation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_candidate_wired_via_shell_docker_push_scores_done(db_session, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "build-deploy.yml").write_text(_SHELL_PUSH_WORKFLOW)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_deployment_automation(db_session, scoring_run, criterion, [])

    assert score.value == 10.0


def test_malformed_workflow_file_treated_as_not_wired(db_session, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "build-push.yml").write_text(": not: valid: yaml: [")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_deployment_automation(db_session, scoring_run, criterion, [])

    assert score.value == 5.0
