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
- [x] FEAT-023 - Promote `Finding`/`Recommendation` data into `ImprovementTask`/`RoadmapItem` rows so the dashboard's roadmap tab is populated automatically: grouped by `(criterion_id, file)` (bypassed, one finding per task, for dependency circularity, code duplication, and any finding with no file), `priority` computed as `worst_severity_in_group x files_impacted / files_to_fix` (float, 1 decimal), upserted by a stable group key so a human-set status/estimated_effort/done_at survives a re-audit the same way `Finding.fingerprint` already does (FEAT-022). Runs automatically at the end of every `radar-audit score`
- [x] FEAT-024 - Add an "Export as md" link to the dashboard's roadmap tab: downloads `roadmap-corrections.md`, items sorted by category (H2) then criterion (H3), each rendered as a checkbox (checked when `DONE`) followed by its description, title stripped of its redundant criterion-name prefix

## Section 8 - Continuous tracking and re-audits

Not yet decomposed into tasks; task IDs assigned when planning starts for this section.

- [ ] Re-audit after implementation work
- [ ] Detect resolved/new/regressed findings with evidence
- [x] FEAT-022 - Persist human verdicts (`FALSE_POSITIVE`/`WONT_FIX`) across re-audits via a stable per-finding fingerprint (criterion + severity + file + a normalized, non-volatile label, hashed; deliberately excludes the line number and any other value that changes on unrelated edits -- see `docs/work-in-progress/finding-fingerprint-design.md`), since `Finding` rows are fully deleted and recreated on every `radar-audit score` pass
- [x] FEAT-025 - Add a weighted risk history chart to the dashboard's Trends tab: per scoring run, open non-false-positive findings stacked by severity, each weighted geometrically (CRITICAL x64, HIGH x16, MEDIUM x4, LOW x1, INFO x0, defined once in `radar_core.enums.SEVERITY_RISK_WEIGHT`) so the trend shows high-severity risk being prioritized; served by `score-history` (`risk`, `risk_index`)
- [x] FEAT-026 - Exclude false-positive findings from the report display and from score computation: severity counts leave them out, each criterion lists them in a collapsed "Dismissed as false positive" section where the verdict can be reverted (score side done per normalizer in FIX-023; `WONT_FIX` findings still count)
- [x] FEAT-027 - Show the weighted risk of the displayed scoring run at the top of the report as a full-width bar, one segment per severity sized by its weighted value, with each severity's count, weight and weighted value as text (blue bar when the risk is 0); same rule as the FEAT-025 trend, served by the report endpoint (`risk`, `risk_index`)
- [x] FEAT-028 - Explain the gap between the risk bar and the severity counts: each severity in the risk bar legend notes its accepted `WONT_FIX` findings, out of the risk but still in the score (`wont_fix` on each risk entry)
- [x] FEAT-029 - Add Playwright end-to-end tests to the dashboard, run in CI: a throwaway seeded SQLite database (`scripts/seed_e2e_db.py`) behind a real `radar-api`, covering the repository list, the report (risk bar, severity counts, dismissed findings), Trends and a verdict change
- [x] FEAT-030 - Audit scope: tests and migrations leave the criteria that judge application code only (complexity, hotspots, module size, dead code, docstrings, duplication, type-checking); lint keeps tests, security keeps everything. Zones defined once in `radar_audit/scope.py`, applied per tool; dead code still analyzes tests as callers and drops their own findings. Rule, rationale and score impact in `docs/quality-framework.md` §3.6
- [x] FEAT-031 - Structured logging with structlog, configured once in `radar_core.observability`: JSON on stderr (readable text in a terminal), one `request_handled` line per API request, audit and tool lifecycle events correlated by `audit_id`; documented in `docs/operations.md` (Logging) with an optional Loki/Alloy/Grafana guide (`docs/guides/log-aggregation.md`)
- [ ] Open question: evaluate an on-demand, possibly partial per-criterion score recalculation -- i.e. a "recalculate this criterion" action a user can trigger once one or more of its findings has `human_verdict != UNREVIEWED` or `status != OPEN`, instead of requiring a full re-audit for the score to reflect a dismissal. Closely related to the score-exclusion bullet above (same per-normalizer banding complication) but framed as an explicit user-triggered action rather than an automatic exclusion
- [x] REFACTOR-001 - Remove the code duplication jscpd reports in radar-audit, behavior unchanged: normalizers share `save_criterion_score`, `band_value`, `worst_of`, `score_pass_rate` and `add_tool_finding` (`normalizers/shared.py`); runners share `run_timed`, `tool_output`, `raw_fallback`, file counting and skip lists (`runners/shared.py`) and one JUnit parser (`runners/junit.py`). Report queries shared with radar-api and dashboard duplication left for later tasks
- [x] REFACTOR-002 - Remove the code duplication jscpd reports in the dashboard, rendering unchanged: a `useExpandedSet` composable for the severity toggles, a `ChartPointList` component for the charts' accessible "View as list", merged toggle styles in the score chart, and global `.page-title` / `.button-primary` classes in `tokens.css`
- [x] CHORE-007 - Cover the dashboard in the pre-commit gate (`eslint` + `oxlint`, `prettier`, `vue-tsc` through its npm scripts) and in CI (lint and format check added next to the type-check); reformat the dashboard once with prettier and fix its last lint error; `CONTRIBUTING.md` lists every hook and CI check
- [x] FEAT-032 - Explanatory note on a dismissed finding: optional `Finding.verdict_note` (200 characters), carried across re-audits with the verdict and dropped when the verdict is reverted, set through `PATCH /findings/{id}/note`; in the dashboard, a "Why" field on false-positive or non-open findings suggests a short fixed list of reasons as you type (native `<datalist>`), with an info hint
- [x] FEAT-033 - Confirm a saved verdict note: a check mark appears right of the "Why" field once the API accepts the note, and goes away as soon as the text is edited again; announced as "Saved" to screen readers through a status region
- [x] CHORE-008 - Harden the Python Dockerfiles for hadolint: `uv` pinned to an exact version (`uv==0.13.7`, the version the images already ran) and the runtime user given by numeric id (`USER 1000`) in `radar-api` and `radar-audit`
- [x] FIX-028 - README completeness detected common section names only by exact keyword ("usage" was never found, so 7 was the practical ceiling): headers inside code blocks are now ignored, common synonyms count ("Installation", "Quick start" for setup and usage, "How it works"...), and a line linking to an existing local `.md` doc credits the sections it names; rule in `docs/quality-framework.md` (8.1)
- [x] FEAT-034 - Tell implemented criteria apart: `Criterion.implemented`, synced from radar-audit's normalizer registry on every `score` (backfilled from past scores by the migration), exposed on criteria and categories (a category is implemented when one of its criteria is) by the report and score-history endpoints; the report shows "Not implemented yet" instead of a score, with the planned criteria of an unimplemented category collapsed, and Trends greys out those categories with a tooltip
- [x] FEAT-035 - List what radar-audit cannot score yet last: the report and score-history endpoints put unimplemented categories after the implemented ones, and unimplemented criteria at the end of their category, keeping the taxonomy order within each group (report and Trends buttons follow)
- [x] FIX-029 - Scoring, re-audit cleanup, report and roadmap promotion crashed with "too many SQL variables" on a run with more findings than SQLite's bound-parameter cap (32766; Summit-Stats has about 63,000): every query that bound one parameter per finding id now uses a subquery instead (report-review finding #17)
- [x] FEAT-036 - Page the findings of large criteria: the report sends the first 1000 findings of each criterion, sorted in SQL, with server-side counts for the severity chips and dismissed findings; a "More" link loads the next 1000 from a new criterion findings endpoint (Summit-Stats has 28,510 type-checking findings)
- [x] FIX-030 - PHPStan analysed files git ignores, its own cache first: 28,492 of the 28,510 Summit-Stats type-checking findings came from `storage/phpstan/cache`; the runner now excludes every git-ignored path (cache, `node_modules`, `bootstrap/cache`...) and reports file paths relative to the repository, like the other runners
- [x] FIX-031 - Every runner skips git-ignored files: phpdoc-checker also analysed PHPStan's cache on Summit-Stats (5,373 of its 5,421 documentation findings, with `node_modules`); the audit plan now lists git-ignored paths once and passes them to every runner, replacing the PHPStan-only exclusion of FIX-030
- [x] DOCS-010 - Refresh the documentation after a month of changes: root and package READMEs (new radar-dashboard README), architecture docs, operations (services, migrations, CI, Docker audit limits), developer guide, CONTRIBUTING (French twin resynced, broken links fixed), product context, and dated amendments in the toolchain and quality framework for adopted candidate tools, FIX-023, FIX-031 and FEAT-034
- [ ] Detect roadmap <-> code divergence
- [ ] Track system self-metrics (score stability, false-positive rate, reproducibility)
