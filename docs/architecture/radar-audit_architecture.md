[🇫🇷 Version française](radar-audit_architecture.fr.md) | 🇬🇧 English version

---

# radar-audit architecture

`radar-audit` orchestrates tool execution against a repository and
normalizes the raw results into the `radar-core` data model. It is
invoked as one-shot CLI commands (`radar-audit run`, `score`, `report`), not a
long-running service, and never mutates the audited repository.

## Pipeline

```text
portfolio.yaml
    ↓
PortfolioConfig (config.py)
    ↓
resolve_repository / get_or_create_audit (orchestrator.py)
    ↓
discover_subprojects (discovery.py)    compute_exclude_paths + compute_ignored_paths (worktree.py)
    ↓                                              ↓
plan_audit → AuditPlan (subprojects, exclude_paths, ignored_paths)
    ↓
planned_runs (AuditPlan × DEFAULT_RUNNERS, filtered by stack/scope)
    ↓
execute_audit: each ToolRunner.run() invoked with crash isolation, its
exclude_paths = worktrees + git-ignored paths + its excluded_zones (scope.py)
    ↓
ToolResult rows (raw_output preserved as-is)          ← end of `radar-audit run`
    ↓
score_repository (scoring.py)                         ← `radar-audit score`
    seed taxonomy, sync Criterion.implemented
    normalizers/*.py: raw_output → Finding / Score, per criterion
    carry human verdicts forward by Finding.fingerprint
    promote findings → ImprovementTask / RoadmapItem (roadmap_promotion.py)
    category scores, then global score
    ↓
render_report (report.py) → Markdown file             ← `radar-audit report`
```

## Responsibilities

- **`config.py`**: loads and validates `portfolio.yaml` (`repos_root` + repository list); raises `PortfolioConfigError` rather than failing silently on a malformed config.
- **`discovery.py`**: detects sub-projects inside a repository by manifest file (`pyproject.toml`/`requirements.txt` -> python, `package.json` -> javascript, `composer.json` -> php), one level deep plus the repo root itself; falls back to a single `unknown`-stack sub-project when no manifest is found.
- **`worktree.py`**: computes the paths every runner must skip: linked worktrees (`compute_exclude_paths`, from `git worktree list`), so nested worktrees are never double-counted, and git-ignored paths (`compute_ignored_paths`, from `git ls-files --others --ignored --exclude-standard --directory`), with a fully ignored directory listed once.
- **`scope.py`**: defines the out-of-scope zones (tests, migrations) and finds their paths (`out_of_scope_paths`); the orchestrator adds them to the `exclude_paths` of each runner whose `excluded_zones` lists them.
- **`gitignore.py`**: matches file paths against the audited repo's root `.gitignore` only (no nested `.gitignore`); used by `static_loc_runner`.
- **`orchestrator.py`**: resolves the `Repository`/`Audit` rows (keyed on `commit_sha`, reused on re-run against an unchanged commit), builds the `AuditPlan`, filters runners by `stack`/`scope`, and executes each run with per-tool crash isolation so one failing tool never aborts the whole audit.
- **`runner.py`**: defines the `ToolRunner` protocol (`tool_name`, `tool_version`, `supported_stacks`, `scope`, `timeout_s`, `run()`, plus an optional `excluded_zones`) that every tool integration implements, and the `RawToolOutput` dataclass every `run()` returns.
- **`runners/`**: one `ToolRunner` implementation per external tool or repo check. The registered list is `cli.DEFAULT_RUNNERS` (34 runners), for example: architecture (dependency-cruiser, pydeps), code quality (ruff, ESLint, mypy, PHPStan, radon, jscpd, knip), tests (pytest coverage, Vitest, Pest, Playwright presence), CI (pre-commit gate, CI workflow, actionlint), security (pip-audit, pnpm audit, composer audit, gitleaks, Semgrep, Trivy, hadolint).
- **`normalizers/`**: one function per criterion, mapping a `ToolResult.raw_output` (or a set of them, or the repo itself for some criteria without a runner) to `Finding`/`Score` rows. The `CRITERION_NORMALIZERS` registry in `normalizers/__init__.py` is the source of truth: a criterion is implemented if and only if it is registered there. Findings marked false positive are still stored but left out of every score.
- **`scoring.py`**: `score_repository` scores the latest audit of a repository: seeds the taxonomy, syncs `Criterion.implemented` from the registry, runs every normalizer, carries human verdicts forward by fingerprint, promotes findings to the roadmap, then writes category and global scores.
- **`roadmap_promotion.py`**: groups findings into `ImprovementTask`/`RoadmapItem` rows by criterion and file; dependency circularity and code duplication get one task per finding.
- **`report.py`**: renders the latest scoring run of a repository as Markdown and writes it to disk.
- **`taxonomy/seed.py`**: idempotently seeds the Quality Framework v1.0 taxonomy (`MethodologyVersion`/`Category`/`Criterion` rows) from a YAML source of truth, so the taxonomy in the database always matches the frozen methodology document.
- **`cli.py`**: the Typer entrypoint, registering `DEFAULT_RUNNERS` and wiring the pipeline above to a `radar-core` session: `run <repo>|--all [--dry-run] [--config path]` stores tool results, `score <repo>` scores them, `report <repo> [--output-dir]` writes the Markdown report (default `radar-audit/reports/<repo>/latest.md`). The entry point configures logging and Sentry; expected errors print a message and exit 1, only unexpected crashes reach Sentry.

## Key design decisions

- **Crash isolation per tool.** A runner that crashes or times out produces a failed `ToolResult` rather than aborting the audit; every other runner still executes.
- **Stack/scope filtering happens at planning time.** `planned_runs()` cross-references each sub-project's detected stack against each runner's `supported_stacks`, and its `scope` (`repo` vs `subproject`) against the sub-project layout, so language-specific tools never run against the wrong stack.
- **Worktrees and git-ignored paths are excluded globally**, not per runner: `compute_exclude_paths` and `compute_ignored_paths` run once per audit and their result is threaded into every runner's `exclude_paths`, since several early runners independently double-counted nested worktree files before this was centralized.
- **Tests and migrations are excluded per criterion**: only runners whose `excluded_zones` name them skip them, so a criterion such as test coverage still sees the tests.
- **Human verdicts survive re-audits.** A verdict, status or note set on a finding is carried to the matching finding of the next scoring run through `Finding.fingerprint`.
- **`--dry-run` never touches the database or invokes any external tool**; it only prints the resolved plan, which makes it safe to use for debugging `portfolio.yaml` or stack detection.
- **Never assumes a database location.** `RADAR_DATABASE_URL` must be set explicitly for any non-dry-run invocation; see [`docs/operations.md`](../operations.md#secrets) for the reasoning.

## Adding a new normalization increment

See the ["Adding a new tool runner"](../guides/developer_guide.md#adding-a-new-tool-runner) section of the developer guide for the concrete steps.
