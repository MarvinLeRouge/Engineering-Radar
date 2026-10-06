[🇫🇷 Version française](roadmap.fr.md) | 🇬🇧 English version

---

# Roadmap

Published, versioned mirror of the project's development roadmap. The
working, non-versioned tracker (updated more frequently during active
development) lives at `docs/work-in-progress/TODO.md`.

Tracks progress section by section. Checkboxes are updated as each task
completes (ticked when its PR merges to `main`).

## Section 1 - Audit system architecture

- [x] DOCS-001 - Design the audit system architecture and produce `docs/system-design.md` plus architecture decision records
  - Inspect the available local environment
  - Identify potentially concerned repositories (read-only, no content changes)
  - Identify the stacks in use
  - Analyze project constraints
  - Propose the overall system architecture
  - Propose the data structure
  - Propose the initial taxonomy
  - Propose the scoring system
  - Propose the confidence system
  - Propose the methodology versioning strategy
  - Propose the roadmap strategy
  - Propose the dashboard architecture
  - Propose the candidate tool list
  - Identify points requiring a human decision
  - Produce `docs/system-design.md`
  - Produce architecture decision records (`docs/adr/`)
  - Human review of the open decisions, blocked Section 2 until resolved

## Section 2 - Toolchain discovery and selection

- [x] DOCS-002 - Evaluate and document the final toolchain (`docs/toolchain.md`)
  - Evaluate candidate tools per language/domain (security, Python, JS/TS, PHP, architecture/dependencies, containers, Git/CI)
  - Validate local availability and licensing of retained tools
  - Document the final toolchain and rejected alternatives (`docs/toolchain.md`)

## Section 3 - Final definition of categories, rules, criteria, scoring

- [x] DOCS-003 - Freeze Quality Framework v1.0 (`docs/quality-framework.md`)
  - Finalize the taxonomy (categories + justified adjustments)
  - Define measurable criteria per category (objective, evidence, tools, levels, weight, dependencies, confidence, false positives)
  - Define the hierarchical scoring model (criterion -> category -> global)
  - Define critical penalties, N/A handling, missing-data handling
  - Freeze **Quality Framework v1.0** (`docs/quality-framework.md`)

## Section 4 - Calibration on a pilot repository

- [x] DOCS-004 - Run pilot calibration audits and correct the framework accordingly
  - Select the pilot repository (see `docs/pilot-audit-geochallenge-tracker.md`)
  - Run a full audit against it (manual pass)
  - Review criteria relevance, false positives/negatives, weights, effort
  - Run a second pilot audit on a structurally different repository (Laravel/PHP + Vue/JS, see `docs/pilot-audit-summit-stats.md`) to check cross-repo consistency
  - Correct the framework based on findings
  - Confirm Quality Framework v1.0 as the reference for the first global audit

## Section 5 - System implementation

- [x] FEAT-001 - Implement the data model (Repository, Audit, MethodologyVersion, Category, Criterion, Finding, Score, Evidence, Recommendation, ImprovementTask, RoadmapItem, Snapshot, ToolResult)
- [ ] Implement tool orchestration and raw-result normalization
  - [x] FEAT-002 - Core orchestration engine (`radar-audit`): portfolio config, sub-project discovery, worktree exclusion, `ToolRunner` protocol with crash isolation, Quality Framework v1.0 taxonomy seeding, Repository/Audit resolution, Typer CLI
  - [ ] Raw-result normalization per Quality Framework category (one task per category)
    - [x] FEAT-003 - Category 1 - Architecture & design: dependency-cruiser + pydeps, DESIGN.md/ARCHITECTURE.md/ADR presence, radon + static LOC module size
    - [x] FEAT-004 - Category 2 - Code quality: lint pass rate, type-check pass rate, cyclomatic complexity, pre-commit gate, code duplication
    - [x] FEAT-005 - Category 3 - Testing & reliability: unit test pass rate, integration tests, CI test execution, E2E test presence
    - [x] FEAT-006 - Category 4 - Security: dependency vulnerabilities (pip-audit/pnpm audit/Composer audit), secrets in git history (Gitleaks), SAST findings (Semgrep), container image vulnerabilities (Trivy), Dockerfile hardening (Hadolint)
    - [x] FEAT-007 - Category 5 - Maintainability: complexity hotspots (reuses the category 2 complexity runners), dead code / unused exports (Vulture, Knip, PHPMD unusedcode), documentation-in-code (docvet, phpdoc-checker; JS/TS is a permanent N/A, no candidate tool)
    - [ ] DOCS-005 - Category 6 - Performance: deferred, not built (its one criterion, Lighthouse-based frontend performance, is the first in the system requiring the audited repo's own running server; decision recorded in `docs/quality-framework.md` section 4.6, revisit after a dedicated live-execution-tooling design session)
    - [x] FEAT-013 - Category 7 - DevOps/CI-CD: CI presence & health (actionlint), Traefik local/prod environment parity, container build hardening (reuses Hadolint evidence), deployment automation
    - [x] FEAT-014 - Category 8 - Documentation: README completeness (heuristic section-header match), Architecture documentation (shares evidence with 1.2), API documentation (FastAPI/Laravel L5-Swagger presence, N/A otherwise)
    - [x] FEAT-015 - Category 9 - Observability / operations: Structured logging (structured-logging library presence), Error tracking integration (Sentry presence + env-sourced DSN check), Health-check endpoint (shares the long-lived-service N/A logic with 7.2/D11)
    - [ ] Categories 10-15 (API/UX/product quality, Dependency management, Configuration management, Data quality, Developer experience, Technical debt) - task IDs assigned when each is started
- [x] Reporting and publication pipeline (see `docs/work-in-progress/reporting-pipeline-notes.md` for the detailed breakdown, dependencies, and tooling)
  - [x] FEAT-008 - A. Extend the report contract to render Findings and an explicit three-state model per criterion (scored / not applicable with reason / not yet audited), reusing the existing `Score.na_reason` field and `FindingSeverity` vocabulary rather than inventing new statuses. Evidence/Recommendation rendering deferred until those tables have a producer (see B)
  - [x] FEAT-009 - B. Populate `Recommendation` records from findings, so improvement axes are stored data feeding the report, not just report prose
  - [x] FEAT-010 - C. Build a minimal `radar-api` (FastAPI): read endpoints over the existing data model, plus narrow human-confirmed-only write endpoints; this is what hosts all report/finding/recommendation data, never written into audited repos
  - [x] FEAT-011 - D. Add a quality-assessment badge (shields.io-style endpoint badge) that audited repos can link from their README, pointing at the radar-hosted report page
  - [x] FEAT-012 - E. Build the full `radar-dashboard` (Vue 3 + Vite SPA): score gauges as discrete flat-color bands (reusing the `FindingSeverity` 5-tier palette, not a continuous gradient) for a professional, non-gimmicky look; N/A and not-yet-audited criteria rendered grayed out with the reason surfaced
  - [x] FEAT-016 - F. Add a generic `Finding.magnitude` field and a shared severity-then-magnitude sort (`radar_core.finding_ordering`), wired into both the CLI report and the `radar-api` report endpoint, so findings of equal severity surface the worst offender first

## Section 6 - Full portfolio audit

Not yet decomposed into tasks; task IDs assigned when planning starts for this section.

- [ ] Run the audit across all identified repositories
- [ ] Generate global documents (`executive-summary`, `portfolio-scorecard`, `cross-project-analysis`, etc.)
- [ ] Generate per-repository documents

## Section 7 - Backlog and roadmap construction

Not yet decomposed into tasks; task IDs assigned when planning starts for this section.

- [ ] Convert findings into prioritized improvement tasks
- [ ] Compute ROI indicators (impact/effort/risk reduction, clearly marked as estimates)
- [ ] Publish the living roadmap

## Section 8 - Continuous tracking and re-audits

Not yet decomposed into tasks; task IDs assigned when planning starts for this section.

- [ ] Re-audit after implementation work
- [ ] Detect resolved/new/regressed findings with evidence
- [ ] Detect roadmap <-> code divergence
- [ ] Track system self-metrics (score stability, false-positive rate, reproducibility)
