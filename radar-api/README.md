[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# radar-api

Minimal FastAPI service for [Engineering-Radar](../README.md).

`radar-api` exposes read endpoints over the Engineering-Radar data
model (repositories, audits, scores, findings, roadmap) plus narrow,
human-confirmed-only write endpoints.

## Required environment variables

- `RADAR_DATABASE_URL` — same SQLite database used by `radar-core`/`radar-audit`.
- `RADAR_API_KEY` — required for all write (`PATCH`) endpoints; requests without
  a valid `X-API-Key` header matching this value receive `401`.

## Endpoints

### Read endpoints

- `GET /repositories` — list all repositories with their latest audit status and global score.
- `GET /repositories/{repository_id}` — repository detail.
- `GET /repositories/{repository_id}/report` — full quality report (categories, criteria, findings, recommendations) for the latest scoring run.
- `GET /repositories/{repository_id}/badge` — shields.io-compatible badge payload for the latest global score.
- `GET /repositories/{repository_id}/findings` — findings for the latest scoring run, optionally filtered by `status` and `severity` query params.
- `GET /repositories/{repository_id}/roadmap` — roadmap items linked to the repository's findings.

### Write endpoints (require `X-API-Key`)

- `PATCH /findings/{finding_id}/verdict` — update a finding's human verdict.
- `PATCH /findings/{finding_id}/status` — update a finding's status.
- `PATCH /roadmap-items/{roadmap_item_id}/status` — update a roadmap item's status; transitioning to `DONE` requires a `done_evidence_id` referencing an `Evidence` row linked to one of the roadmap item's findings.

## Running locally

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    export RADAR_API_KEY="your-secret-key"
    uv run --package radar-api uvicorn radar_api.main:app --reload

## Database migrations

`radar-api` does not run migrations itself, it expects the database already
migrated via `radar-core`'s Alembic setup:

    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

On a fresh Docker volume, nothing runs migrations automatically, this step
must be run manually (e.g. by overriding the `radar-audit` container's
entrypoint, or running the command locally against the same database file)
before the API's endpoints will work. Without it, every endpoint returns a
`500`.

## Docker

    docker compose build radar-api
    docker compose up radar-api

`RADAR_API_KEY` must be set in the shell environment before `docker compose up`
(referenced via `${RADAR_API_KEY}` in `docker-compose.yml`). `RADAR_PORTFOLIO_PATH`
only matters for the separate `radar-audit` CLI profile.

`radar-api` is wired to the shared Traefik instance (same convention as the
other `marvinlerouge` projects): the `traefik-public` external network,
`Host(\`radar-api.marvinlerouge.local\`)` on the `web` entrypoint locally. The
production router (`radar-api.marvinlerouge.dev`, `websecure`/`letsencrypt`)
is not wired yet, this repository has no production compose file so far.

## Quality badge

Any repository audited by Engineering-Radar can link a
shields.io [endpoint badge](https://shields.io/badges/endpoint-badge) in its
README, sourced from `GET /repositories/{repository_id}/badge`. Nothing
else (no report content, no scores) is ever written into the audited
repository itself, only this one Markdown line:

    [![Quality](https://img.shields.io/endpoint?url=https%3A%2F%2Fradar-api.marvinlerouge.dev%2Frepositories%2F{repository_id}%2Fbadge)](https://radar-api.marvinlerouge.dev/repositories/{repository_id}/report)

Replace `{repository_id}` with the repository's numeric id in Radar's
database. Locally, swap the domain for `radar-api.marvinlerouge.local`.

The link currently points at the raw `/report` JSON endpoint (no
human-friendly report page exists yet, that's item E, the `radar-dashboard`
SPA). Once the dashboard ships, the link target should move to the
dashboard's per-repository report page instead.

## Running tests

    uv run --package radar-api pytest

## Known limitations

- Using `httpx` with `starlette.testclient` currently emits a `DeprecationWarning` in tests (test-only, no runtime effect); no action needed unless the dependency stack changes.
- The service does not validate `RADAR_DATABASE_URL` / `RADAR_API_KEY` at startup, a missing or misconfigured value surfaces as a `500` (database URL) or a `401` on every write (API key) rather than a startup failure. Tracked as a follow-up.
- SQLite WAL mode is not yet enabled, concurrent API reads and `radar-audit` writes to the same database file may occasionally hit "database is locked". Tracked as a follow-up (belongs in `radar-core`).
