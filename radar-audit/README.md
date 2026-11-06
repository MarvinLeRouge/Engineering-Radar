[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# radar-audit

Tool orchestration and normalization engine for [Engineering-Radar](../README.md).

`radar-audit` discovers a repository's sub-projects, runs the deterministic
analysis tools relevant to each detected stack, and persists their raw
results against the versioned Quality Framework taxonomy. Scoring then turns
those results into scores, findings, recommendations and roadmap items. See
[`docs/quality-framework.md`](../docs/quality-framework.md) for the full
methodology and [`docs/toolchain.md`](../docs/toolchain.md) for how each
tool was selected.

## Coverage

34 tool runners (`DEFAULT_RUNNERS` in `src/radar_audit/cli.py`) feed 30
implemented criteria (`CRITERION_NORMALIZERS` in
`src/radar_audit/normalizers/__init__.py`) across categories 1, 2, 3, 4, 5, 7,
8 and 9. Category 6 (Performance) is deferred, since its only criterion needs
the audited repository's running server; categories 10 to 15 are not started.

| Category | Main tools |
|---|---|
| 1. Architecture & design | dependency-cruiser, pydeps, Radon (raw), static LOC count, design-doc presence |
| 2. Code quality | Ruff, ESLint, Pint, mypy, tsc, PHPStan, Radon, ESLint complexity, PHPMD, pre-commit gate, jscpd |
| 3. Testing & reliability | pytest-cov, Vitest, Pest, integration-test heuristic, CI workflow inspection, Playwright presence |
| 4. Security | pip-audit, pnpm audit, composer audit, gitleaks, Semgrep, Trivy (images), hadolint |
| 5. Maintainability | Radon, ESLint complexity, PHPMD, Vulture, Knip, docvet, phpdoc-checker |
| 7. DevOps / CI-CD | actionlint, hadolint; Traefik parity and deployment automation read the repository at scoring time |
| 8. Documentation | none: the repository is read at scoring time |
| 9. Observability / operations | none: the repository is read at scoring time |

## What is excluded

- For every runner: linked git worktrees and every git-ignored path.
- For application-code runners: migrations always, and tests too for module
  size, type-checking, complexity, duplication and docstrings (lint and dead
  code still read tests). Set per runner through `excluded_zones`
  (`src/radar_audit/scope.py`).
- For runners scoped to a sub-project: the other sub-projects nested under it.

## Prerequisites

`radar-audit` writes to the same SQLite database as `radar-core`'s Alembic
migrations. Before running a real (non-dry-run) audit for the first time,
apply the migrations against the target database:

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

## Usage

Run from the repository root, with `RADAR_DATABASE_URL` set (or `.env`
sourced). The local run is the supported way: the `cli` Docker profile image
is a plain Python image without the analysis tools (Composer, npx, Docker), so
it cannot run a full audit.

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-audit radar-audit run <repo-name>
    uv run --package radar-audit radar-audit run --all
    uv run --package radar-audit radar-audit run <repo-name> --dry-run
    uv run --package radar-audit radar-audit score <repo-name>
    uv run --package radar-audit radar-audit report <repo-name>

- `run` stores the raw tool results only. `--all` audits every repository of
  `portfolio.yaml`, `--config` points at another portfolio file. `--dry-run`
  prints the excluded worktrees, the number of git-ignored paths, the
  sub-projects and the planned runners, without touching the database.
- `score` normalizes the latest audit into scores, findings, recommendations
  and roadmap items.
- `report` writes a Markdown report of the latest score, by default to
  `radar-audit/reports/<repo-name>/latest.md` (git-ignored, `--output-dir` to
  change it).

Repository scope and the local checkout root (`repos_root: ~/projets`) are
configured in `portfolio.yaml` (versioned in this directory).
