# radar-audit — Category 7 (DevOps / CI-CD) Runners (Increment 2.7) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Increment 2.6 (category 6, Performance) was
> brainstormed and resolved as deferred, not built — see `docs/quality-framework.md`§4.6's
> 2026-09-30 note. This increment resumes strict taxonomic order at category 7. Builds on
> increments 2.1-2.5 (categories 1-5), all merged to `main`. Binome review is folded into this
> increment's own subagent-driven-development workflow, per the 2026-09-24 process update.
> Spec references: `docs/quality-framework.md`§4.7 (criteria catalog), `docs/work-in-progress/open-decisions.md`
> D11 (Traefik criterion, category 7), `docs/toolchain.md` (actionlint entry),
> `docs/superpowers/specs/2026-09-23-radar-audit-category-4-security-design.md` (Trivy/Hadolint
> runners reused by 7.3), `docs/superpowers/specs/2026-08-29-radar-audit-category-2-code-quality-design.md`
> (2.4 pre-commit gate, the coverage-ratio precedent this spec follows instead of D11's original,
> never-built `PENDING_CONFIRMATION` human-confirmation-gate mechanism).

---

## 1. Scope

Seventh of the fifteen category increments (2.1-2.15, strict numeric order). Covers **category 7,
DevOps / CI-CD**:

| # | Criterion (exact taxonomy name) | Archetype | Tool(s) | In this increment? |
|---|---|---|---|---|
| 7.1 | CI presence & health | A | actionlint (Docker, already validated) | Yes |
| 7.2 | Reverse proxy / local-prod environment parity (Traefik) | C | none — static `docker-compose*.yml` parsing | Yes |
| 7.3 | Container build hardening | A | hadolint (reused from 4.5, no new runner) | Yes |
| 7.4 | Deployment automation | C | none — static GitHub Actions workflow parsing | Yes |

No criterion is deferred out of this increment. Two new `ToolRunner`s (`ActionlintRunner` for 7.1,
covered by the existing Docker-runner pattern), two normalizer-only additions with no runner at
all (7.2, 7.4 — pure static YAML parsing, no subprocess), and one normalizer-only addition reusing
an existing runner's output unchanged (7.3, reuses `HadolintRunner`'s `ToolResult` rows already
produced for criterion 4.5).

**7.2's design was validated empirically against the three repositories already in `radar.db`**
(GeoChallenge-Tracker, HexaRot, Summit-Stats) before this spec was written — see §4.

## 2. Goal

Repeat the normalization pattern established in 2.1-2.5 (raw `ToolResult` -> `Finding`/`Score` at
criterion level) for category 7. No infrastructure changes are needed to the `ToolRunner`
protocol, orchestrator, or data model — the taxonomy YAML is already fully seeded for category 7
(`quality_framework_v1_0.yaml`, category `order: 7`), confirmed before design started.

This increment's one resolved ambiguity worth calling out up front: `docs/work-in-progress/open-decisions.md`
D11 (the original decision introducing 7.2) specifies a system-wide **human-confirmation gate**
(a criterion's status transition to its maximal state is held `PENDING_CONFIRMATION` pending
explicit human confirmation, whenever supporting evidence is not `HIGH` confidence). Confirmed
before design started: **this mechanism was never implemented anywhere in the codebase**
(`grep -r "PENDING_CONFIRMATION\|human_confirmation" radar-core/src radar-audit/src` returns
nothing), and criterion 2.4 (pre-commit gate, which also cross-references D11/D12) was built
without it, scoring a computed coverage ratio directly instead. 7.2 follows the same, already
-established precedent: a computed coverage score, no confirmation-gate infrastructure built or
assumed.

## 3. Runners — 7.1 CI presence & health

**`ActionlintRunner`** (`scope="repo"`, `supported_stacks=frozenset()`, `tool_name="actionlint"`)

Modeled directly on `HadolintRunner` (`radar_audit/runners/hadolint_runner.py`), the existing
Docker-runner pattern (`run_docker_command`, already used by Gitleaks/Trivy/Hadolint in category
4). `docs/toolchain.md` already lists `actionlint` as validated ("**Keep**", smoke-tested on
GeoChallenge-Tracker, 2 real findings) — no new tool validation needed before this increment.

Invocation: `docker run --rm -v <target_path>:/repo -w /repo rhysd/actionlint:latest -format
'{{json .}}'`, no per-file discovery loop needed (unlike Hadolint) — actionlint auto-discovers
`.github/workflows/` itself with no path argument, per `toolchain.md`'s existing entry. If
`.github/workflows/` does not exist at all, `run_docker_command` still executes but actionlint
exits 0 with an empty findings array — the runner does not special-case this, the normalizer
below does (returns "no data" rather than a false "clean" score). `raw_output = {"findings":
[<actionlint JSON row>, ...]}`, the tool's own JSON array parsed as-is. Usable exit codes: `{0,
1}` (0 = clean, 1 = findings present — actionlint's own documented convention, confirmed already
during toolchain validation).

## 4. Normalizer — 7.2 Reverse proxy / local-prod environment parity

No runner. `normalize_traefik_parity` reads `docker-compose.yml` and a candidate prod compose
file directly from `target_path` (repo scope, no `ToolResult` involved at all — same "static
config inspection, no subprocess" shape as `PlaywrightPresenceRunner`, just reading two files
instead of checking one config's presence).

**Candidate prod filenames, tried in order, first match wins:** `docker-compose.prod.yml`,
`docker-compose.production.yml`, `compose.prod.yml`, `compose.prod.yaml`. `docker-compose.prod.yml`
first per the user's explicit instruction (2026-09-30) — it is the convention observed on all
three repositories already in `radar.db`, confirmed by direct inspection of their real compose
files during this design session.

**Algorithm**, validated against the same three repositories before this spec was written:

1. Parse `docker-compose.yml` (local). If absent, criterion has no data (`None`, not `N/A` — a
   repo with no `docker-compose.yml` at all is out of this criterion's applicable population
   entirely, same treatment as "no data" elsewhere in this framework, not an active exclusion).
2. Try each prod-filename candidate in order; parse the first one found. If none exist, criterion
   scores `N/A` — "no production compose file found", same population logic already used for D11
   ("repos with no long-lived service", cross-referenced by 9.3's health-check N/A rule).
3. For each file, collect the set of top-level `services` keys whose `labels` (list or dict form,
   both handled — Compose supports either) include `traefik.enable=true` (exact match after
   stripping surrounding quotes).
4. `both` = services with Traefik labels in **both** files (same service key name in both —
   simple identity match, no fuzzy/rename handling, confirmed acceptable by the user 2026-09-30).
   `union` = services with Traefik labels in **either** file. A service with no Traefik labels in
   either file (e.g. an internal-only service like `maildev`) never enters `union` — it is
   excluded from the ratio entirely, not penalized, since it never opted into being
   Traefik-routed.
5. If `union` is empty (no service anywhere uses Traefik), criterion scores `N/A` — "no
   Traefik-routed services found in either compose file".
6. Otherwise: `value = (len(both) / len(union)) * 10`, archetype-C "computed" mode (same coverage
   formula as 2.4's pre-commit gate), confidence `HIGH` (static YAML parsing, no tool-output
   ambiguity to hedge against).

**Empirical validation (this session, before the spec was written)** — all three repositories in
`radar.db`:

| Repo | Local Traefik services | Prod Traefik services | `both`/`union` | Score |
|---|---|---|---|---|
| GeoChallenge-Tracker | `{backend, frontend, tiles}` | `{backend, frontend, tiles}` | 3/3 | 10.0 |
| HexaRot | `{backend, frontend}` | `{backend, frontend}` | 2/2 | 10.0 |
| Summit-Stats | `{nginx}` | `{nginx}` | 1/1 | 10.0 |

All three score a clean 10.0, correctly excluding non-Traefik-routed internal services
(`maildev` in GeoChallenge-Tracker) from the denominator rather than penalizing the repo for
them.

No `Finding` rows generated for a perfect or partial match (a missing-parity gap is visible
directly in the score + the service-level detail is not the kind of individually-actionable
"remove this line" finding the `Finding` model is used for elsewhere) — a lower score is
sufficient signal on its own, consistent with how 7.1 and 1.1 score without generating a finding
per missing item either. One exception: for each service present in `union` but not in `both`
(a genuine parity gap, not just "never used Traefik"), add a `Finding` naming the service and
which side (local/prod) is missing the label, `severity=LOW`, so the report can point at exactly
which service to fix.

## 5. Normalizer — 7.3 Container build hardening

No runner. `normalize_container_build_hardening` reads the same `ToolResult` rows `HadolintRunner`
already produces for criterion 4.5 (`tool_name == "hadolint"`), via the same `tool_results` list
every normalizer receives (`score_repository` selects all `ToolResult` rows for the audit
up-front, filtered by `tool_name` inside each normalizer — confirmed against
`docstring_coverage.py`'s existing cross-tool-inspection pattern, no new plumbing needed).

**Deliberately a different formula from 4.5's**, not a duplicate: 4.5 (`dockerfile_hardening.py`,
`normalize_dockerfile_hardening`) computes `(clean_dockerfiles / total_dockerfiles) * 10` — a
binary per-file "has zero findings" ratio, a Security-framed "is this image's build definition
free of known bad patterns" question. 7.3 instead counts the total number of hadolint findings
across every Dockerfile (not per-file binary), and bands the count — a DevOps-framed "how much
build-hygiene debt exists in this pipeline" question, the same severity-density style already
used by 5.2's dead-code banding rather than 4.5's clean-ratio style. This is the concrete
resolution of the open point flagged during brainstorming (2026-09-30): a distinct score computed
from the same raw evidence, not the same numeric value under two headings.

`finding_count` = total hadolint findings across all `dockerfiles` entries in every relevant
`ToolResult` (same "error entries excluded, not counted as zero findings" rule as 4.5's own
normalizer — reused verbatim via `has_success_payload`). No `Finding` rows generated by 7.3 itself
— 4.5 already created one `Finding` per hadolint finding against the same evidence; duplicating
them under a second criterion would double-report the same issue, same principle already applied
to 5.1 versus 2.3 (§3.1 of the category-5 spec).

| finding_count | Score |
|---|---|
| 0 | 10.0 |
| 1-3 | 8.0 |
| 4-8 | 6.0 |
| 9-15 | 4.0 |
| >15 | 2.0 |

Confidence: `HIGH` (reuses hadolint's already-`HIGH`-confidence evidence, per 4.5's own
normalizer). If no relevant `ToolResult` exists for the run (no Dockerfile found, hadolint never
ran), criterion has no data (`None`) — same "no data" treatment as 7.1's missing-workflow case,
not `N/A` (a repo could plausibly add a Dockerfile later; this is not a structural non-applicability
like "no UI" is for 6.1).

## 6. Normalizer — 7.4 Deployment automation

No runner. `normalize_deployment_automation` reads `.github/workflows/*.yml` directly from
`target_path` (repo scope, static parsing — same shape as 7.2, no subprocess).

**Algorithm**, validated against the same three repositories:

1. List every file under `.github/workflows/`. If the directory does not exist, criterion has no
   data (`None`) — same "out of applicable population, no active exclusion" treatment as 7.2's
   step 1.
2. A workflow file is a **deployment-automation candidate** if its filename matches
   `build-push.yml`, `build-deploy.yml`, `deploy.yml`, or `release.yml` (the first two confirmed
   as the real naming convention across all three repositories in `radar.db`; `deploy.yml`/
   `release.yml` added as reasonable additional candidates, not yet observed in this portfolio —
   flagged for recalibration once Phase 5's full portfolio audit surfaces more examples).
3. Parse each candidate file. It counts as **wired to a registry push step** if any job step's
   `uses` field starts with `docker/build-push-action` AND that step's `with.push` is `true` (not
   `false`/absent — a build-only dry run does not count), OR any `run` step's shell script
   contains the literal substring `docker push` (a fallback for repos not using the GitHub Action,
   not yet observed in this portfolio but a reasonable manual-push pattern).
4. If no deployment-automation candidate file exists at all: `TODO`, `value=0.0`.
5. If at least one candidate exists but none are wired to a registry push step: `IN_PROGRESS`,
   `value=5.0` (per the archetype-C default for a partially-adopted practice — a workflow exists
   but doesn't actually publish anywhere yet).
6. If at least one candidate is wired to a registry push step: `DONE`, `value=10.0`.

Confidence: `MEDIUM` (per `quality-framework.md`§4.7's existing note: "presence only, no runtime
verification of actual deploys" — a workflow can exist and be correctly wired but never actually
have run successfully; that verification is explicitly out of scope, flagged in the catalog as a
future possibility via GitHub API run-history access, not built here).

**Empirical validation (this session)**: all three repositories have a matching candidate file
(`build-push.yml` for GeoChallenge-Tracker, `build-deploy.yml` for HexaRot and Summit-Stats),
each confirmed containing `docker/build-push-action@v6` with `push: true` targeting `ghcr.io` —
all three would score `DONE` / 10.0.

No `Finding` rows — same reasoning as 7.2: the score itself (TODO/IN_PROGRESS/DONE) is the
signal, there is no individually-actionable line-level finding to point at for "no deployment
workflow exists."

## 7. Error handling and N/A

- **7.1**: actionlint execution failures (Docker daemon unreachable, timeout) follow the exact
  same `RawToolOutput` fallback-to-`{"stdout", "stderr"}` pattern as every existing Docker-based
  runner — never raises, normalizer excludes unusable results and returns `None` (no data) rather
  than crashing the scoring run.
- **7.2, 7.4**: YAML parse failures (malformed `docker-compose.yml`, malformed workflow YAML) are
  caught per-file; a file that fails to parse is treated as absent for that step (same "no data"
  treatment as a missing file), not as a crash — static-file normalizers have no subprocess to
  fail, so the only failure mode is a parse error, handled locally in the normalizer itself
  (no `ToolRunner`/`RawToolOutput` involved for these two).
- **7.3**: no new failure mode — reuses 4.5's already-handled `HadolintRunner` failures as-is.
- No new critical-penalty (P1-P4) interaction — category 7 criteria produce `Finding`/`Score` rows
  at `ScoreLevel.CRITERION` only, same scope boundary every prior category has used.

## 8. Testing plan

Mirrors the existing test structure exactly:

- **`test_actionlint_runner.py`**: command construction (Docker invocation, no per-file loop
  unlike Hadolint), parsing of a real actionlint JSON payload (captured against GeoChallenge
  -Tracker's actual 2 findings, already referenced in `toolchain.md`), the no-`.github/workflows`
  case, malformed-output fallback.
- **`test_normalize_ci_health.py`**: table-driven on exit-code/finding-count combinations, the
  "no data" path when no `ToolResult` exists.
- **`test_normalize_traefik_parity.py`**: table-driven using the three real repositories' actual
  compose files captured as fixtures during this session's validation (§4) plus synthetic edge
  cases — no `docker-compose.yml` at all (no data), no prod candidate found (`N/A`), a service
  present only in local (partial `both`/`union`, generates one `Finding`), prod-filename
  candidate-order (a repo with both `docker-compose.prod.yml` and `compose.prod.yaml` present
  uses the first).
- **`test_normalize_container_build_hardening.py`**: table-driven on exact band boundaries (3 vs.
  4 findings), confirms it reuses `hadolint` `ToolResult` rows without requiring a new runner
  registration, confirms it does not duplicate `Finding` rows already created by 4.5's normalizer
  against the same `ToolResult`.
- **`test_normalize_deployment_automation.py`**: table-driven on the three states (no candidate
  file / candidate present but not wired / candidate wired to `docker/build-push-action` with
  `push: true`), using the three real repositories' actual workflow files as fixtures, plus the
  `docker push` shell-command fallback path (synthetic, not yet observed in this portfolio).
- No new test infrastructure required — real fixtures captured during this session's empirical
  validation (§4, §6) seed realistic test data directly, same approach as category 5's spec.
