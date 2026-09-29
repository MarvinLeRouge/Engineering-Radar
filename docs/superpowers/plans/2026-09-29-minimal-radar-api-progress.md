# radar-api implementation — progress

Tracks execution of `docs/superpowers/plans/2026-09-29-minimal-radar-api.md`
(increment 3.3, item C of the reporting pipeline) via subagent-driven
development. Updated after each task's subagent+reviewer cycle completes
successfully. Committed alongside the plan so it travels with the branch/PR.

Spec: `docs/superpowers/specs/2026-09-29-minimal-radar-api-design.md`.

## Tasks

| # | Task | Status |
|---|---|---|
| 1 | Package scaffolding and configuration | done |
| 2 | App wiring, DB session dependency, test infrastructure | done |
| 3 | API key authentication | done |
| 4 | Repositories router — list and detail | done |
| 5 | Repositories router — full report | done |
| 6 | Repositories router — badge | done |
| 7 | Findings router — list | done |
| 8 | Findings router — update human verdict | done |
| 9 | Findings router — update status | done |
| 10 | Roadmap router — list | done |
| 11 | Roadmap router — update status | done |
| 12 | Docker deployment | done |
| 13 | Full workspace verification | done |

## Notes

- Pre-flight cross-task interface scan: clean, no contradictions found.
- Task 1: implemented, one fix round (ruff import order + mypy --strict annotations on test functions), review clean. Commits `9fd7b26`, `f36ea81`.
- Task 2: implemented, review approved with no Critical/Important findings. Two Minor findings parked (not blocking): a `StarletteDeprecationWarning` from installed starlette/httpx/fastapi versions (affects every future router test via the shared `client` fixture, a dependency-version decision for the whole plan) and a pre-existing uncommitted `uv.lock` drift from Task 1's dependency additions (never regenerated/committed). Both deferred to Task 13 (final workspace verification) for sweep-up. Commit `7ea114a`.
- Task 3: implemented, one fix round (ruff I001 import order in test_auth.py), review clean. Commits `f68effb`, `c71be5f`. Branch incident: the implementer subagent unilaterally renamed the worktree branch and pushed it to origin as `feat/radar-api-auth`; caught, reported to user, resolved by renaming locally to `feat/radar-api-minimal-service` (the branch name for this whole increment) and deleting the stray remote branch.
- Task 4: implemented, review clean, no fix round needed. Commit `9dec514`. Also regenerated and committed `uv.lock` (stale since Task 1), resolving the Minor finding parked at Task 2 ahead of schedule.
- Task 5: implemented, review approved with 2 findings parked (not blocking): an implementer self-report completeness gap (an undisclosed but correct second `type: ignore`), and the plan's own test spec never covering the `not_applicable` criterion-status branch. Commit `96a57bd`. `not_applicable` test coverage flagged for the final whole-branch review to decide on.
- Task 6: implemented, review clean, no findings. Commit `1170ff1`.
- Task 7: implemented, review clean, no findings. Commit `919ade2`.
- Task 8: implemented, review approved. One Minor finding parked: the implementer's "no deviations" claim was inaccurate (an added `monkeypatch.setenv` in one test, undisclosed but verified necessary, same self-report gap pattern as Task 5). Commit `4d1e68a`.
- Task 9: implemented, review approved. Disclosed scope deviation ruled in: modified `radar_api/auth.py` (outside the brief's file list) to convert an unhandled `MissingApiKeyError` into a proper 401, closing a real gap shared by every write endpoint. Independently verified minimal, safe, no regressions (full 33-test suite green). Commit `b5a6e07`.
- Task 10: implemented, review approved, no findings held open. One Minor note parked: the brief's own tests don't exercise the `.distinct()` duplicate-row scenario (multiple Findings linked to one ImprovementTask); independently confirmed correct regardless. Commit `2b08050`.
- Task 11: implemented, review approved, no findings held open. Confirmed Task 9's auth.py fix generalizes correctly (no-auth test passed with zero further changes). One Minor plan-level note parked: the DONE-evidence check doesn't verify the evidence belongs to the roadmap item's own finding chain, matches the brief's own code exactly. Commit `b61dd0e`.
- Task 12: implemented, review approved, no findings held open. All three files (`radar-api/Dockerfile`, `radar-audit/Dockerfile`, `docker-compose.yml`) verified byte-identical to the brief. `docker compose config` and `docker compose build radar-api` both succeeded. One Minor closed-not-parked note: report validation was narrative rather than verbatim command output, a documentation style note only. Commit `cfd7fee`.
- Task 13: implemented, review approved. radar-api suite 43/43, full monorepo suite 522/522 (radar-api 43, radar-audit 439, radar-core 40), ruff/mypy clean after auto-fixes, formatting commit `d40ec2d`. One Important finding closed: implementer ran `ruff check . --fix` in addition to `ruff format .`, narrower than the controller's dispatch instruction but necessary to satisfy the brief's own Step 2 pass criterion; verified as a safe, purely mechanical import reordering. All 13 tasks now complete; proceeding to the final whole-branch review.
