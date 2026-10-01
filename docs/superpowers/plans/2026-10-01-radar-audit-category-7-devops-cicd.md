# radar-audit Category 7 (DevOps / CI-CD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** add `radar-audit` support for category 7 (DevOps/CI-CD)'s 4 criteria: CI presence &
health (7.1), Traefik local/prod parity (7.2), container build hardening (7.3), and deployment
automation (7.4) — one new `ToolRunner`, three normalizer-only additions (one reusing an existing
runner's output, two reading the repository's own files directly with no runner at all), all
registered into the existing `DEFAULT_RUNNERS`/`CRITERION_NORMALIZERS` tables.

**Architecture:** repeats the established raw-`ToolResult` -> `Finding`/`Score` normalization
pattern from increments 2.1-2.5. No changes to the `ToolRunner` protocol, the orchestrator, or the
data model. One new shared helper (`get_repository_path`) lets a normalizer resolve the audited
repo's on-disk path from `scoring_run` alone, for the two criteria with no runner at all.

**Tech Stack:** Python 3.12, `uv` workspace (`radar-audit` package), SQLModel (via `radar-core`),
PyYAML (already a project dependency, used elsewhere for taxonomy seeding), Docker (for the new
`ActionlintRunner`, same `run_docker_command` helper already used by Gitleaks/Trivy/Hadolint),
pytest.

**Spec:** `docs/superpowers/specs/2026-09-30-radar-audit-category-7-devops-cicd-design.md`

## Global Constraints

- Exact taxonomy criterion names (already seeded in `quality_framework_v1_0.yaml`, category
  `"DevOps / CI-CD"`): `"CI presence & health"`, `"Reverse proxy / local-prod environment parity
  (Traefik)"`, `"Container build hardening"`, `"Deployment automation"`.
- 7.3 reuses `HadolintRunner`'s existing `ToolResult` rows (`tool_name == "hadolint"`) — no new
  runner for 7.3, and its score must be computed independently from 4.5's (a distinct
  finding-count-banded formula, not the same value under a second heading).
- 7.2 and 7.4 have no `ToolRunner` at all — they read the repository's own files directly via the
  new `get_repository_path(session, scoring_run)` helper, not via `tool_results`.
- Prod compose filename candidates, tried in this exact order, first match wins:
  `docker-compose.prod.yml`, `docker-compose.production.yml`, `compose.prod.yml`,
  `compose.prod.yaml`.
- A service counts as Traefik-routed when its `labels` (list or dict form) contain
  `traefik.enable=true` (quotes stripped before comparing).
- Deployment-automation candidate workflow filenames: `build-push.yml`, `build-deploy.yml`,
  `deploy.yml`, `release.yml`. Wired to a registry push = a step whose `uses` starts with
  `docker/build-push-action` and `with.push is True`, OR a `run` step containing the literal
  substring `docker push`.
- `actionlint` usable exit codes are `{0, 1}` only — **empirically confirmed during planning**:
  exit code `3` ("no project was found...") is what actionlint returns both when
  `.github/workflows/` does not exist and when the target isn't a git repository at all; this
  must be treated as "no data" (`None`), never as a false "clean" (10.0) result. This corrects an
  unstated assumption in the merged spec (§3), which did not anticipate this exit code.
- No `Finding` rows duplicated against evidence another criterion already reported on (7.3 must
  not re-create `Finding`s against the same `hadolint` payload 4.5's normalizer already created
  them from).

## Review Focus

1. A repository with no `.github/workflows/` directory at all (or a target that isn't a git repo)
   must score 7.1 as "no data" (`None`), not as a false 10.0 "clean" result — `actionlint`'s real
   exit code for this case is `3`, not `0`. Pinned in Task 2.
2. A malformed/unparsable `docker-compose.yml` or workflow YAML file must not crash the whole
   `score` run — it must be treated the same as "file absent" for that step. Pinned in Tasks 3 and
   5.
3. A repository where a service has Traefik labels in the local compose file but not the prod one
   (or vice versa) must generate a `Finding` naming the service and the missing side, and score
   strictly between 0 and 10 — not silently treated as either fully compliant or fully absent.
   Pinned in Task 3.
4. 7.3's normalizer must not create a second `Finding` row for a `hadolint` finding 4.5's
   normalizer already turned into a `Finding` against the same `ToolResult` — only `Score` differs
   between the two criteria, not the finding ledger. Pinned in Task 4.
5. A repository with zero Dockerfiles at all (hadolint never produced a `ToolResult` for it) must
   score 7.3 as "no data" (`None`), not crash, and not silently score a perfect 10.0 as if build
   hardening were flawless with nothing to check. Pinned in Task 4.

---

### Task 1: `ActionlintRunner`

**Files:**
- Create: `radar-audit/src/radar_audit/runners/actionlint_runner.py`
- Modify: `radar-audit/src/radar_audit/cli.py` (register in `DEFAULT_RUNNERS`)
- Test: `radar-audit/tests/test_actionlint_runner.py`

**Interfaces:**
- Produces: `radar_audit.runners.actionlint_runner.ActionlintRunner` (a `ToolRunner`,
  `tool_name="actionlint"`), consumed by Task 2's normalizer via `tool_results` filtered on
  `tool_name == "actionlint"`.

**Design note — empirically confirmed during planning (real `docker run` invocations, not
assumed):** `rhysd/actionlint:latest -format '{{json .}}'` against a real git repo with a clean
workflow prints `[]` and exits `0`. Against one shellcheck-style issue (`run: echo $FOO`,
unquoted) it exits `1` and prints a JSON array of finding objects (`message`, `filepath`, `line`,
`column`, `kind`, `snippet`). Against a repo with **no** `.github/workflows/` directory at all
(even if the repo has other tracked files), or a target that isn't a git repository, it exits `3`
and prints a plain-text error (`"no project was found in any parent directories of "/repo"...`),
**not valid JSON** — this must be captured as an `"error"` payload, not parsed as a findings list.

- [ ] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_actionlint_runner.py
from radar_audit.runners.actionlint_runner import ActionlintRunner

from tests.git_helpers import init_git_repo

_CLEAN_WORKFLOW = """\
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "hello"
"""

_DIRTY_WORKFLOW = """\
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo $FOO
"""


def test_reports_no_findings_for_a_clean_workflow(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _CLEAN_WORKFLOW})

    runner = ActionlintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"findings": []}


def test_reports_a_shellcheck_finding_for_an_unquoted_variable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _DIRTY_WORKFLOW})

    runner = ActionlintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    findings = result.raw_output["findings"]
    assert len(findings) == 1
    assert findings[0]["kind"] == "shellcheck"
    assert findings[0]["filepath"] == ".github/workflows/ci.yml"


def test_reports_an_error_payload_when_no_workflows_directory_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"a.txt": "x\n"})

    runner = ActionlintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 3
    assert "error" in result.raw_output
    assert "findings" not in result.raw_output


def test_reports_tool_identity():
    runner = ActionlintRunner()

    assert runner.tool_name == "actionlint"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-audit && uv run pytest tests/test_actionlint_runner.py -v`
Expected: FAIL (`radar_audit.runners.actionlint_runner` does not exist)

- [ ] **Step 3: Implement the runner**

```python
# radar-audit/src/radar_audit/runners/actionlint_runner.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command


class ActionlintRunner:
    """Lints GitHub Actions workflows with actionlint (criterion 7.1)."""

    tool_name = "actionlint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        completed, duration_ms = run_docker_command(
            [
                "-v",
                f"{target_path}:/repo",
                "-w",
                "/repo",
                "rhysd/actionlint:latest",
                "-format",
                "{{json .}}",
            ],
            timeout_s=self.timeout_s,
        )

        findings = self._parse_findings(completed.stdout)
        if findings is None:
            return RawToolOutput(
                command="docker run ... actionlint -format '{{json .}}'",
                raw_output={"error": completed.stderr.strip()},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command="docker run ... actionlint -format '{{json .}}'",
            raw_output={"findings": findings},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _parse_findings(stdout: str) -> list[dict[str, object]] | None:
        stripped = stdout.strip()
        if not stripped:
            return []
        try:
            findings = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        return findings if isinstance(findings, list) else None
```

- [ ] **Step 4: Register in `DEFAULT_RUNNERS`**

In `radar-audit/src/radar_audit/cli.py`, add the import alongside the other runner imports
(alphabetical, between `ActionlintRunner` would sort before `CiWorkflowRunner`):

```python
from radar_audit.runners.actionlint_runner import ActionlintRunner
```

Add to the `DEFAULT_RUNNERS` list (anywhere in the list; append at the end, after
`HadolintRunner()`):

```python
    ActionlintRunner(),
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-audit && uv run pytest tests/test_actionlint_runner.py -v`
Expected: PASS (4 tests). Requires Docker to be running locally — same precondition every
existing Gitleaks/Trivy/Hadolint test already has.

- [ ] **Step 6: Commit**

```bash
git add radar-audit/src/radar_audit/runners/actionlint_runner.py radar-audit/src/radar_audit/cli.py radar-audit/tests/test_actionlint_runner.py
git commit -m "feat(radar-audit): add ActionlintRunner for criterion 7.1"
```

---

### Task 2: `normalize_ci_health` (7.1)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/ci_health.py`
- Modify: `radar-audit/src/radar_audit/normalizers/__init__.py` (register in
  `CRITERION_NORMALIZERS`)
- Test: `radar-audit/tests/test_normalize_ci_health.py`

**Interfaces:**
- Consumes: `ActionlintRunner`'s `ToolResult` rows (Task 1), `add_finding_with_recommendation`
  (`radar_audit.normalizers.shared`, already exists).
- Produces: `radar_audit.normalizers.ci_health.normalize_ci_health`, registered under
  `("DevOps / CI-CD", "CI presence & health")`.

**Design note:** the merged spec did not specify a banding table for 7.1 (only the runner's
behavior). Resolved here, reusing 5.2's/7.3's established finding-count-banded shape for
consistency rather than inventing a new scale: `0 -> 10.0`, `1-3 -> 8.0`, `4-8 -> 6.0`,
`9-15 -> 4.0`, `>15 -> 2.0`. Usable exit codes are `{0, 1}` only (see Global Constraints) — exit
code `3` (or any other) means "no data", `None`, same treatment as every other tool's unusable
exit code elsewhere in this codebase.

- [ ] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_normalize_ci_health.py
from radar_audit.normalizers.ci_health import normalize_ci_health
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
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
        db_session, methodology_version.id, "DevOps / CI-CD", "CI presence & health"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output, exit_code=0):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="actionlint",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=exit_code,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_usable_tool_result_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"error": "no project was found"}, exit_code=3
    )

    score = normalize_ci_health(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_clean_workflow_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"findings": []})

    score = normalize_ci_health(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_two_findings_scores_eight_and_creates_findings(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "message": "shellcheck issue",
                    "filepath": ".github/workflows/ci.yml",
                    "line": 8,
                    "kind": "shellcheck",
                },
                {
                    "message": "another issue",
                    "filepath": ".github/workflows/ci.yml",
                    "line": 10,
                    "kind": "syntax-check",
                },
            ]
        },
        exit_code=1,
    )

    score = normalize_ci_health(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 8.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 2
    assert findings[0].file == ".github/workflows/ci.yml"
    assert findings[0].line == 8
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_ci_health.py -v`
Expected: FAIL (`radar_audit.normalizers.ci_health` does not exist)

- [ ] **Step 3: Implement the normalizer**

```python
# radar-audit/src/radar_audit/normalizers/ci_health.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_finding_with_recommendation

_USABLE_EXIT_CODES = {0, 1}
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (3, 8.0), (8, 6.0), (15, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0
_RECOMMENDATION_TEXT = (
    "Fix the actionlint finding (workflow syntax issue or embedded shell-script problem)."
)


def normalize_ci_health(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "actionlint"
        and r.exit_code in _USABLE_EXIT_CODES
        and isinstance(r.raw_output, dict)
        and isinstance(r.raw_output.get("findings"), list)
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    findings_payload = tool_result.raw_output["findings"]

    for finding in findings_payload:
        add_finding_with_recommendation(
            session,
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.LOW,
                description=finding.get("message", "actionlint finding"),
                file=finding.get("filepath"),
                line=finding.get("line"),
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            ),
            _RECOMMENDATION_TEXT,
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(len(findings_payload)),
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(finding_count: int) -> float:
    for max_count, value in _BANDS:
        if finding_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE
```

- [ ] **Step 4: Register in `CRITERION_NORMALIZERS`**

In `radar-audit/src/radar_audit/normalizers/__init__.py`, add the import:

```python
from radar_audit.normalizers.ci_health import normalize_ci_health
```

Add to the `CRITERION_NORMALIZERS` dict:

```python
    ("DevOps / CI-CD", "CI presence & health"): normalize_ci_health,
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_ci_health.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/ci_health.py radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/tests/test_normalize_ci_health.py
git commit -m "feat(radar-audit): add normalize_ci_health for criterion 7.1"
```

---

### Task 3: `get_repository_path` helper + `normalize_traefik_parity` (7.2)

**Files:**
- Modify: `radar-audit/src/radar_audit/normalizers/shared.py` (add `get_repository_path`)
- Create: `radar-audit/src/radar_audit/normalizers/traefik_parity.py`
- Modify: `radar-audit/src/radar_audit/normalizers/__init__.py` (register in
  `CRITERION_NORMALIZERS`)
- Test: `radar-audit/tests/test_normalize_traefik_parity.py`

**Interfaces:**
- Produces: `radar_audit.normalizers.shared.get_repository_path(session, scoring_run) -> Path`
  (also consumed by Task 5's `normalize_deployment_automation`),
  `radar_audit.normalizers.traefik_parity.normalize_traefik_parity`, registered under
  `("DevOps / CI-CD", "Reverse proxy / local-prod environment parity (Traefik)")`.

**Design note:** this is the first normalizer with no `ToolRunner`/`ToolResult` at all — it reads
`docker-compose.yml` and a candidate prod compose file directly from the repository's own path,
resolved via the new `get_repository_path` helper (`ScoringRun.audit_id` -> `Audit.repository_id`
-> `Repository.path`, no new field or migration needed — `Repository.path` already exists).

- [ ] **Step 1: Write the failing test for `get_repository_path`**

```python
# radar-audit/tests/test_normalizers_shared.py
from radar_audit.normalizers.shared import get_or_create_scoring_run, get_repository_path
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository


def test_get_repository_path_resolves_from_scoring_run(db_session):
    repo = Repository(name="repo", path="/tmp/repo-under-test")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)

    path = get_repository_path(db_session, scoring_run)

    assert str(path) == "/tmp/repo-under-test"
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalizers_shared.py -v`
Expected: FAIL (`get_repository_path` does not exist)

- [ ] **Step 3: Implement `get_repository_path`**

Add to `radar-audit/src/radar_audit/normalizers/shared.py` (new imports at the top, new function
anywhere in the file):

```python
from pathlib import Path

from radar_core.models.repository import Repository
```

```python
def get_repository_path(session: Session, scoring_run: ScoringRun) -> Path:
    """Resolve the on-disk path of the repository being scored.

    For normalizers that read the audited repo's own files directly (no
    ToolRunner/ToolResult involved), unlike every other normalizer in this module.
    """
    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None
    repository = session.get(Repository, audit.repository_id)
    assert repository is not None
    return Path(repository.path)
```

- [ ] **Step 4: Run it, confirm it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalizers_shared.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Write the failing tests for `normalize_traefik_parity`**

```python
# radar-audit/tests/test_normalize_traefik_parity.py
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.traefik_parity import normalize_traefik_parity
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


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
        db_session,
        methodology_version.id,
        "DevOps / CI-CD",
        "Reverse proxy / local-prod environment parity (Traefik)",
    )
    return scoring_run, criterion


_TRAEFIK_LABELS = """\
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app.rule=Host(`example.local`)"
"""


def test_no_local_compose_file_returns_none(db_session, tmp_path):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score is None


def test_no_prod_candidate_found_scores_na(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(f"services:\n  app:\n{_TRAEFIK_LABELS}")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_no_traefik_anywhere_scores_na(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services:\n  app:\n    image: nginx\n")
    (tmp_path / "docker-compose.prod.yml").write_text("services:\n  app:\n    image: nginx\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.na_reason is not None


def test_full_parity_scores_ten(db_session, tmp_path):
    compose = f"services:\n  backend:\n{_TRAEFIK_LABELS}  frontend:\n{_TRAEFIK_LABELS}  db:\n    image: postgres\n"
    (tmp_path / "docker-compose.yml").write_text(compose)
    (tmp_path / "docker-compose.prod.yml").write_text(compose)
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
    assert score.na_reason is None


def test_partial_parity_scores_between_zero_and_ten_and_creates_a_finding(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(
        f"services:\n  backend:\n{_TRAEFIK_LABELS}  frontend:\n{_TRAEFIK_LABELS}"
    )
    (tmp_path / "docker-compose.prod.yml").write_text(f"services:\n  backend:\n{_TRAEFIK_LABELS}")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 5.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert "frontend" in findings[0].description


def test_malformed_compose_file_treated_as_absent(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(": not: valid: yaml: [")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score is None


def test_prod_filename_candidate_order_prefers_docker_compose_prod(db_session, tmp_path):
    (tmp_path / "docker-compose.yml").write_text(f"services:\n  app:\n{_TRAEFIK_LABELS}")
    (tmp_path / "docker-compose.prod.yml").write_text(f"services:\n  app:\n{_TRAEFIK_LABELS}")
    (tmp_path / "compose.prod.yaml").write_text("services:\n  app:\n    image: nginx\n")
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session, tmp_path)

    score = normalize_traefik_parity(db_session, scoring_run, criterion, [])

    assert score.value == 10.0
```

- [ ] **Step 6: Run them, confirm they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_traefik_parity.py -v`
Expected: FAIL (`radar_audit.normalizers.traefik_parity` does not exist)

- [ ] **Step 7: Implement the normalizer**

```python
# radar-audit/src/radar_audit/normalizers/traefik_parity.py
from __future__ import annotations

from pathlib import Path

import yaml
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import add_finding_with_recommendation, get_repository_path

_LOCAL_COMPOSE_FILENAME = "docker-compose.yml"
_PROD_COMPOSE_CANDIDATES = (
    "docker-compose.prod.yml",
    "docker-compose.production.yml",
    "compose.prod.yml",
    "compose.prod.yaml",
)
_NO_PROD_FILE_NA_REASON = "No production compose file found (no long-lived service to proxy)"
_NO_TRAEFIK_NA_REASON = "No Traefik-routed services found in either compose file"


def normalize_traefik_parity(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)

    local_services = _traefik_services(target_path / _LOCAL_COMPOSE_FILENAME)
    if local_services is None:
        return None

    prod_path = _find_prod_compose(target_path)
    if prod_path is None:
        return _na_score(session, scoring_run, criterion, _NO_PROD_FILE_NA_REASON)

    prod_services = _traefik_services(prod_path)
    if prod_services is None:
        return _na_score(session, scoring_run, criterion, _NO_PROD_FILE_NA_REASON)

    both = local_services & prod_services
    union = local_services | prod_services
    if not union:
        return _na_score(session, scoring_run, criterion, _NO_TRAEFIK_NA_REASON)

    for service in sorted(union - both):
        missing_side = "prod" if service in local_services else "local"
        add_finding_with_recommendation(
            session,
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                severity=FindingSeverity.LOW,
                description=(
                    f"Service '{service}' is Traefik-routed but missing a {missing_side} router"
                ),
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            ),
            f"Add matching Traefik labels for '{service}' to the {missing_side} compose file.",
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(len(both) / len(union)) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _na_score(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, reason: str
) -> Score:
    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=0.0,
        confidence=Confidence.HIGH,
        na_reason=reason,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _find_prod_compose(target_path: Path) -> Path | None:
    for candidate in _PROD_COMPOSE_CANDIDATES:
        candidate_path = target_path / candidate
        if candidate_path.is_file():
            return candidate_path
    return None


def _traefik_services(compose_path: Path) -> set[str] | None:
    if not compose_path.is_file():
        return None
    try:
        data = yaml.safe_load(compose_path.read_text())
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    services = data.get("services")
    if not isinstance(services, dict):
        return set()

    result: set[str] = set()
    for name, definition in services.items():
        if not isinstance(definition, dict):
            continue
        labels = definition.get("labels") or []
        if isinstance(labels, dict):
            labels = [f"{k}={v}" for k, v in labels.items()]
        if any(
            str(label).strip().strip('"').strip("'") == "traefik.enable=true"
            for label in labels
        ):
            result.add(name)
    return result
```

- [ ] **Step 8: Register in `CRITERION_NORMALIZERS`**

In `radar-audit/src/radar_audit/normalizers/__init__.py`, add the import:

```python
from radar_audit.normalizers.traefik_parity import normalize_traefik_parity
```

Add to the `CRITERION_NORMALIZERS` dict:

```python
    (
        "DevOps / CI-CD",
        "Reverse proxy / local-prod environment parity (Traefik)",
    ): normalize_traefik_parity,
```

- [ ] **Step 9: Run tests, confirm they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_traefik_parity.py tests/test_normalizers_shared.py -v`
Expected: PASS (8 tests)

- [ ] **Step 10: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/shared.py radar-audit/src/radar_audit/normalizers/traefik_parity.py radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/tests/test_normalize_traefik_parity.py radar-audit/tests/test_normalizers_shared.py
git commit -m "feat(radar-audit): add get_repository_path and normalize_traefik_parity for criterion 7.2"
```

---

### Task 4: `normalize_container_build_hardening` (7.3)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/container_build_hardening.py`
- Modify: `radar-audit/src/radar_audit/normalizers/__init__.py` (register in
  `CRITERION_NORMALIZERS`)
- Test: `radar-audit/tests/test_normalize_container_build_hardening.py`

**Interfaces:**
- Consumes: `HadolintRunner`'s existing `ToolResult` rows (`tool_name == "hadolint"`, already
  produced for criterion 4.5 — no new runner), `has_success_payload`
  (`radar_audit.normalizers.shared`, already exists).
- Produces: `radar_audit.normalizers.container_build_hardening.normalize_container_build_hardening`,
  registered under `("DevOps / CI-CD", "Container build hardening")`.

**Design note:** deliberately a different formula from 4.5's own `normalize_dockerfile_hardening`
(`(clean_dockerfiles / total_dockerfiles) * 10`, a binary per-file ratio). This normalizer counts
the **total** number of hadolint findings across every Dockerfile and bands the count (same shape
as 5.2's dead-code banding), so the two criteria produce genuinely different numbers from the same
raw evidence rather than duplicating one score under two headings. **No `Finding` rows are created
here** — 4.5's normalizer already created one `Finding` per hadolint finding against the exact
same `ToolResult`; this task must not create a second set against the same evidence (Review Focus
#4).

- [ ] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_normalize_container_build_hardening.py
from radar_audit.normalizers.container_build_hardening import (
    normalize_container_build_hardening,
)
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
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
        db_session, methodology_version.id, "DevOps / CI-CD", "Container build hardening"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output, exit_code=0):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="hadolint",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=exit_code,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_hadolint_tool_result_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [])

    assert score is None


def test_zero_findings_across_all_dockerfiles_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {"dockerfiles": [{"path": "Dockerfile", "findings": []}]},
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_four_findings_across_dockerfiles_scores_six(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {
                    "path": "Dockerfile",
                    "findings": [
                        {"code": "DL3008", "message": "a"},
                        {"code": "DL3009", "message": "b"},
                    ],
                },
                {
                    "path": "backend/Dockerfile",
                    "findings": [
                        {"code": "DL3002", "message": "c"},
                        {"code": "DL3007", "message": "d"},
                    ],
                },
            ]
        },
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0


def test_does_not_duplicate_findings_already_created_by_criterion_4_5(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "findings": [{"code": "DL3008", "message": "a"}]}
            ]
        },
    )

    normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 0


def test_failed_dockerfile_entry_excluded_from_the_count(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "error": "Cannot connect to the Docker daemon"},
                {"path": "backend/Dockerfile", "findings": []},
            ]
        },
        exit_code=1,
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_orchestrator_crash_record_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    crashed = _make_tool_result(
        db_session, audit, {"error": "Command 'docker' timed out after 120 seconds"}, exit_code=-1
    )

    score = normalize_container_build_hardening(db_session, scoring_run, criterion, [crashed])

    assert score is None
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_container_build_hardening.py -v`
Expected: FAIL (`radar_audit.normalizers.container_build_hardening` does not exist)

- [ ] **Step 3: Implement the normalizer**

```python
# radar-audit/src/radar_audit/normalizers/container_build_hardening.py
from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import has_success_payload

_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (3, 8.0), (8, 6.0), (15, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_container_build_hardening(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "hadolint" and has_success_payload(r, "dockerfiles")
    ]
    if not relevant:
        return None

    finding_count = 0
    for tool_result in relevant:
        for entry in tool_result.raw_output["dockerfiles"]:
            findings = entry.get("findings")
            if isinstance(findings, list):
                finding_count += len(findings)

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(finding_count),
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(finding_count: int) -> float:
    for max_count, value in _BANDS:
        if finding_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE
```

- [ ] **Step 4: Register in `CRITERION_NORMALIZERS`**

In `radar-audit/src/radar_audit/normalizers/__init__.py`, add the import:

```python
from radar_audit.normalizers.container_build_hardening import (
    normalize_container_build_hardening,
)
```

Add to the `CRITERION_NORMALIZERS` dict:

```python
    ("DevOps / CI-CD", "Container build hardening"): normalize_container_build_hardening,
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_container_build_hardening.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/container_build_hardening.py radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/tests/test_normalize_container_build_hardening.py
git commit -m "feat(radar-audit): add normalize_container_build_hardening for criterion 7.3"
```

---

### Task 5: `normalize_deployment_automation` (7.4)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/deployment_automation.py`
- Modify: `radar-audit/src/radar_audit/normalizers/__init__.py` (register in
  `CRITERION_NORMALIZERS`)
- Test: `radar-audit/tests/test_normalize_deployment_automation.py`

**Interfaces:**
- Consumes: `get_repository_path` (Task 3).
- Produces: `radar_audit.normalizers.deployment_automation.normalize_deployment_automation`,
  registered under `("DevOps / CI-CD", "Deployment automation")`.

- [ ] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_normalize_deployment_automation.py
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
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_deployment_automation.py -v`
Expected: FAIL (`radar_audit.normalizers.deployment_automation` does not exist)

- [ ] **Step 3: Implement the normalizer**

```python
# radar-audit/src/radar_audit/normalizers/deployment_automation.py
from __future__ import annotations

from pathlib import Path

import yaml
from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import get_repository_path

_CANDIDATE_FILENAMES = frozenset(
    {"build-push.yml", "build-deploy.yml", "deploy.yml", "release.yml"}
)


def normalize_deployment_automation(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    target_path = get_repository_path(session, scoring_run)
    workflows_dir = target_path / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return None

    candidates = [
        p for p in workflows_dir.iterdir() if p.is_file() and p.name in _CANDIDATE_FILENAMES
    ]
    if not candidates:
        value = 0.0
    elif any(_is_wired_to_registry_push(p) for p in candidates):
        value = 10.0
    else:
        value = 5.0

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


def _is_wired_to_registry_push(workflow_path: Path) -> bool:
    try:
        data = yaml.safe_load(workflow_path.read_text())
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if isinstance(uses, str) and uses.startswith("docker/build-push-action"):
                with_block = step.get("with")
                if isinstance(with_block, dict) and with_block.get("push") is True:
                    return True
            run = step.get("run")
            if isinstance(run, str) and "docker push" in run:
                return True
    return False
```

- [ ] **Step 4: Register in `CRITERION_NORMALIZERS`**

In `radar-audit/src/radar_audit/normalizers/__init__.py`, add the import:

```python
from radar_audit.normalizers.deployment_automation import normalize_deployment_automation
```

Add to the `CRITERION_NORMALIZERS` dict:

```python
    ("DevOps / CI-CD", "Deployment automation"): normalize_deployment_automation,
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_deployment_automation.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/deployment_automation.py radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/tests/test_normalize_deployment_automation.py
git commit -m "feat(radar-audit): add normalize_deployment_automation for criterion 7.4"
```

---

### Task 6: Full workspace verification and real-repo validation

**Files:** none created; verification only.

**Design note:** per this project's standing practice ("always validate against a real portfolio
repo before considering an increment done"), this task re-scores the three repositories already
present in the project's own `radar.db` (`GeoChallenge-Tracker`, `HexaRot`, `Summit-Stats`) and
confirms the real numbers match what this plan's design (and the spec's empirical validation
during brainstorming) predicted.

- [ ] **Step 1: Run the full `radar-audit` test suite**

Run: `cd radar-audit && uv run pytest -v`
Expected: PASS, zero failures (includes every test from Tasks 1-5, plus the full existing suite —
confirms no regression)

- [ ] **Step 2: Run `ruff` and `mypy` on `radar-audit`**

Run: `cd radar-audit && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: PASS, no errors

- [ ] **Step 3: Run the full monorepo test suite to confirm no regression**

Run: `uv run pytest` (from repo root)
Expected: PASS, same pass count as before this plan plus this plan's new tests

- [ ] **Step 4: Re-run `radar-audit run --all` and `radar-audit score` against the real portfolio**

Run (from the repo root, with `RADAR_DATABASE_URL` pointed at the project's own `radar.db`):

```bash
export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
uv run --package radar-audit radar-audit run GeoChallenge-Tracker
uv run --package radar-audit radar-audit run HexaRot
uv run --package radar-audit radar-audit run Summit-Stats
uv run --package radar-audit radar-audit score GeoChallenge-Tracker
uv run --package radar-audit radar-audit score HexaRot
uv run --package radar-audit radar-audit score Summit-Stats
uv run --package radar-audit radar-audit report GeoChallenge-Tracker
uv run --package radar-audit radar-audit report HexaRot
uv run --package radar-audit radar-audit report Summit-Stats
```

Expected: no crashes; each `report` output now shows real scores for category 7's four criteria
(category 6 stays "not yet audited", unaffected by this plan). Confirm against this plan's and the
spec's empirical predictions: 7.2 (Traefik parity) scores 10.0/10 for all three repos; 7.4
(deployment automation) scores 10.0/10 for all three repos (all three have a wired
`build-push.yml`/`build-deploy.yml`); 7.1 and 7.3's exact values depend on each repo's real
`actionlint`/`hadolint` output, not predicted in advance — record whatever they actually come out
to, investigate only if a value looks structurally wrong (e.g. `None`/no-data where a workflow or
Dockerfile clearly exists).

- [ ] **Step 5: Commit any final formatting fixes**

```bash
git add -u
git commit -m "chore(radar-audit): apply ruff formatting"
```

(Skip this step entirely if Steps 1-4 made no changes — no empty commits.)
