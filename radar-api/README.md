[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# radar-api

Minimal FastAPI service for [Engineering-Radar](../README.md).

`radar-api` exposes read endpoints over the Engineering-Radar data
model (repositories, audits, scores, findings, roadmap) plus narrow,
human-confirmed-only write endpoints.

## Required environment variables

- `RADAR_DATABASE_URL`: same SQLite database used by `radar-core`/`radar-audit`.
- `RADAR_API_KEY`: required for all write (`PATCH`) endpoints; requests without
  a valid `X-API-Key` header matching this value receive `401`.

## Optional environment variables

- `SENTRY_DSN`, `SENTRY_ENVIRONMENT`: Sentry error tracking, disabled when the
  DSN is empty (in Docker, `SENTRY_DSN` comes from `SENTRY_BACKEND_DSN`).
- `RADAR_LOG_LEVEL` (default `info`), `RADAR_LOG_FORMAT` (`json` or `console`;
  empty means JSON unless stderr is a terminal).

Every request writes one structured `request_handled` log line (method, path,
status, duration; never the query string, headers or body). See
[`docs/operations.md`](../docs/operations.md).

## Endpoints

The interactive OpenAPI documentation is served at `/docs`. There is no health
endpoint.

### Read endpoints

- `GET /repositories`: list all repositories with their latest audit status and global score.
- `GET /repositories/{repository_id}`: repository detail.
- `GET /repositories/{repository_id}/report`: full quality report (categories, criteria, findings, recommendations) for the latest scoring run (or `?scoring_run_id=`), with its `scoring_run_id`, the weighted `risk` per severity and its sum `risk_index`. Each criterion lists its first 1000 findings in priority order, with `findings_total`, `severity_counts` and `dismissed_count` covering all of them. Criteria and categories carry `implemented`; unimplemented ones are listed last.
- `GET /repositories/{repository_id}/report/criteria/{criterion_id}/findings?scoring_run_id=&offset=`: the next pages of a criterion's findings, 1000 at a time, in the same order (latest scoring run when `scoring_run_id` is omitted).
- `GET /repositories/{repository_id}/score-history`: one point per scoring run, oldest first, with the global score, category scores (each with `implemented`), `risk` and `risk_index`.
- `GET /repositories/{repository_id}/badge`: shields.io-compatible badge payload for the latest global score.
- `GET /repositories/{repository_id}/findings`: findings for the latest scoring run, optionally filtered by `status` and `severity` query params.
- `GET /repositories/{repository_id}/roadmap`: roadmap items linked to the repository's findings, sorted by category, criterion, priority (highest first) and title.
- `GET /roadmap-items/{roadmap_item_id}/evidence-candidates`: evidence rows of the findings linked to a roadmap item, usable as its `done_evidence_id`.

### Write endpoints (require `X-API-Key`)

- `PATCH /findings/{finding_id}/verdict`: update a finding's human verdict.
- `PATCH /findings/{finding_id}/status`: update a finding's status.
- `PATCH /findings/{finding_id}/note`: set the short note explaining a finding's verdict (200 characters at most, trimmed; blank text clears it).
- `PATCH /roadmap-items/{roadmap_item_id}/status`: update a roadmap item's status; transitioning to `DONE` requires a `done_evidence_id` referencing an `Evidence` row linked to one of the roadmap item's findings.

## Running locally

Copy `.env.example` (repo root) to `.env`, fill in a real `RADAR_API_KEY`, then
load it into the shell before starting the server (run from the repo root,
not from `radar-api/`):

    set -a && source .env && set +a
    uv run --package radar-api uvicorn radar_api.main:app --reload

Neither `radar-api` nor `radar-audit` loads `.env` automatically (see
`config.py`'s "never assumes a default" policy): it must be sourced in every
new shell. Without a `.env` file, exporting the two variables directly also
works:

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    export RADAR_API_KEY="your-secret-key"
    uv run --package radar-api uvicorn radar_api.main:app --reload

## Database migrations

`radar-api` does not run migrations itself, it expects the database already
migrated via `radar-core`'s Alembic setup:

    set -a && source .env && set +a
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

Nothing runs migrations automatically, and without them every endpoint returns
a `500`. The Docker `radar-data` volume is bound to the host project folder
(`RADAR_PROJECT_PATH`), so the containers use the host `radar.db`: running the
command above locally, from the repo root, is enough. Back up `radar.db`
first.

## Docker

    scripts/rebuild.sh radar-api

`scripts/rebuild.sh` rebuilds the image without cache and restarts the service
(see [`docs/operations.md`](../docs/operations.md)). `RADAR_API_KEY` and
`RADAR_PROJECT_PATH` must be set in the shell environment or `.env` (referenced
in `docker-compose.yml`). `RADAR_PORTFOLIO_PATH`
only matters for the separate `radar-audit` CLI profile.

`radar-api` is wired to the shared Traefik instance (same convention as the
other `marvinlerouge` projects): the `traefik-public` external network,
`Host(\`radar-api.marvinlerouge.local\`)` on the `web` entrypoint locally. The
production router (`radar-api.marvinlerouge.dev`, `websecure`/`letsencrypt`)
is not wired yet, this repository has no production compose file so far. The
dashboard host `radar.marvinlerouge.local` also routes `/api` to `radar-api`
(prefix stripped).

## Quality badge

Any repository audited by Engineering-Radar can link a
shields.io [endpoint badge](https://shields.io/badges/endpoint-badge) in its
README, sourced from `GET /repositories/{repository_id}/badge`. Nothing
else (no report content, no scores) is ever written into the audited
repository itself, only this one Markdown line:

    [![Quality](https://img.shields.io/endpoint?url=https%3A%2F%2Fradar-api.marvinlerouge.dev%2Frepositories%2F{repository_id}%2Fbadge)](https://radar-api.marvinlerouge.dev/repositories/{repository_id}/report)

Replace `{repository_id}` with the repository's numeric id in Radar's
database. Locally, swap the domain for `radar-api.marvinlerouge.local`.

The link still targets the raw `/report` JSON endpoint. The human-readable
report page lives in [`radar-dashboard`](../radar-dashboard/README.md), at
`/repositories/<slug>-<id>`.

## Running tests

    uv run --package radar-api pytest

## Known limitations

- Using `httpx` with `starlette.testclient` currently emits a `DeprecationWarning` in tests (test-only, no runtime effect); no action needed unless the dependency stack changes.
- The service does not validate `RADAR_DATABASE_URL` / `RADAR_API_KEY` at startup, a missing or misconfigured value surfaces as a `500` (database URL) or a `401` on every write (API key) rather than a startup failure. Tracked as a follow-up.
- SQLite WAL mode is not yet enabled, concurrent API reads and `radar-audit` writes to the same database file may occasionally hit "database is locked". Tracked as a follow-up (belongs in `radar-core`).
