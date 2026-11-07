[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# radar-online

Hosted service of [Engineering-Radar](../README.md) that publishes sanitized
reports: the global and category scores of a repository, its trends and a
badge, without any finding. Decisions in
[ADR 0014](../docs/adr/0014-radar-online-public-reports.md), design in
[radar-online design](../docs/radar-online-design.md).

**Status:** scaffold only (CHORE-010). The app starts and answers
`GET /api/health`; accounts, publication, public pages and the badge are the
next tasks of [roadmap Section 9](../docs/roadmap.md).

## Layout

- `src/radar_online/`: FastAPI app (`main.py`), configuration, database session,
  and `models/` (its own tables only, never radar-core's audit data).
- `alembic/`: radar-online's own migrations, on its own SQLite database.
- `tests/`: each test runs on a throwaway, migrated SQLite file.

Every route, the OpenAPI schema (`/api/openapi.json`) and the docs (`/api/docs`)
live under `/api`, since the online dashboard is served on the same host.

## Configuration

- `RADAR_ONLINE_DATABASE_URL` (required): the SQLite URL, never assumed.
- Optional, as for radar-api: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`,
  `RADAR_LOG_LEVEL`, `RADAR_LOG_FORMAT` (see [operations](../docs/operations.md)).

## Development

From the repository root:

    set -a && source .env && set +a
    uv run --package radar-online alembic -c radar-online/alembic.ini upgrade head
    uv run --package radar-online uvicorn radar_online.main:app --reload --port 8010

Tests:

    uv run --package radar-online pytest radar-online/tests --cov=radar_online

## Docker

    scripts/rebuild.sh radar-online

Locally, Traefik exposes it at `radar-online.marvinlerouge.local/api`, with its
database at `<RADAR_PROJECT_PATH>/radar-online.db` (the shared `radar-data`
bind mount). The container does not migrate on start: run the Alembic command
above first. The hosted deployment at `radar.marvinlerouge.dev` comes with
CHORE-012.
