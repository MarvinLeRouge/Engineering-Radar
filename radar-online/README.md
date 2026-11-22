[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# radar-online

Hosted service of [Engineering-Radar](../README.md) that publishes sanitized
reports: the global and category scores of a repository, its trends and a
badge, without any finding. Decisions in
[ADR 0014](../docs/adr/0014-radar-online-public-reports.md), design in
[radar-online design](../docs/radar-online-design.md).

**Status:** data model in place (FEAT-037): users, hashed API keys, single-use
action tokens, published repositories and reports, plus the shared payload
contract `radar_core.publication`; accounts are created by an admin command
(FEAT-050) and reports are uploaded through `POST /api/reports` (FEAT-042).
Public pages and the badge are the next tasks of
[roadmap Section 9](../docs/roadmap.md).

## Layout

- `src/radar_online/`: FastAPI app (`main.py`), configuration, database session,
  `models/` (its own tables only, never radar-core's audit data), `tokens.py`
  (random keys and tokens, stored as SHA-256 hashes), `accounts.py` and
  `cli.py` (the `radar-online` admin command), `auth.py` (API key check) and
  `routers/` (the API endpoints).
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

## Create an account

Until the email registration flow exists, the admin creates each account,
active at once, with its first API key:

    uv run --package radar-online radar-online create-account \
        --email ada@example.com --display-name "Ada" --slug ada

In Docker: `docker compose exec radar-online radar-online create-account ...`.
The key is printed once and only its hash is stored: hand it to its owner and
do not keep it elsewhere. The slug is the public namespace (1 to 64 lowercase
letters, digits or hyphens); email and slug must be unused.

## Upload a report

`POST /api/reports` with the header `X-API-Key` and a v1 publication payload
(`radar_core.publication`, unknown fields rejected) as the JSON body, at most
64 KiB. The repository is created on the first upload under the key owner's
namespace; uploading a commit already published replaces its report (200),
otherwise the report is added (201). The answer gives the public page path,
e.g. `{"report_path": "/u/ada/summit-stats"}`. A missing, unknown or revoked
key, or an account that is not active, gets a 401.

## Docker

    scripts/rebuild.sh radar-online

Locally, Traefik exposes it at `radar-online.marvinlerouge.local/api`, with its
database at `<RADAR_PROJECT_PATH>/radar-online.db` (the shared `radar-data`
bind mount). The container does not migrate on start: run the Alembic command
above first. The hosted deployment at `radar.marvinlerouge.dev` comes with
CHORE-012.
