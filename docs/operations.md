[🇫🇷 Version française](operations.fr.md) | 🇬🇧 English version

---

# Operations

Minimal operations reference. This is a local, single-user, offline-first
system: there is no hosted deployment yet.

## Running the services

`radar-api` and `radar-dashboard` are long-running services started with
Docker Compose, from the repository root, once `.env` is filled in from
`.env.example`:

```bash
docker compose up -d
```

- **Traefik**: both services join the external `traefik-public` network,
  which must exist before the first start (it belongs to the local Traefik
  setup, not to this project). The dashboard answers on
  `radar.marvinlerouge.local`, which also routes `/api` to `radar-api`; the
  API answers on `radar-api.marvinlerouge.local` and on port 8000 of the host.
- **Shared database**: the `radar-data` volume is a bind mount of
  `RADAR_PROJECT_PATH` (the host project folder) on `/data`, so the
  containers read and write the same `radar.db` as a local `uv run`.
- **Permissions**: the Python images run as uid 1000. The host folder
  behind `RADAR_PROJECT_PATH`, and `radar.db` itself, must be writable by
  uid 1000, or every write (verdicts, statuses, notes) fails.
- **API key**: the PATCH endpoints require `RADAR_API_KEY` in the
  `X-API-Key` header; enter it in the dashboard's Settings page (kept
  for the browser session).

## Running the audit

`radar-audit` is a CLI run on demand, not a long-running service. The
supported way to run it is locally, with `uv`, against the portfolio in
`~/projets` (`repos_root` in `radar-audit/portfolio.yaml`):

```bash
uv run radar-audit run some-repo   # runs the tools, stores their raw results
uv run radar-audit score some-repo # turns the latest audit into scores, findings and roadmap items
```

See the [developer guide](guides/developer_guide.md) for setup, `--all`,
`--dry-run` and the Markdown `report` command.

The `cli`-profile Docker image (`docker compose --profile cli run --rm radar-audit`) cannot run
a full audit today: it is a slim Python image without the external tools
many runners call (Node/npx, Composer, PHP, Docker...), and inside it
`~/projets` resolves to `/home/appuser/projets` while the portfolio is
mounted at `/portfolio`. Use the local run.

## Data

All structured audit data lives in the database pointed to by
`RADAR_DATABASE_URL`. For local use this is typically a gitignored SQLite
file; nothing about the schema assumes SQLite specifically (managed via
Alembic migrations in `radar-core`).

Raw tool output captured during a run is kept alongside the normalized
results rather than discarded, so a finding can always be traced back to
the tool invocation that produced it.

There is no backup automation yet: back up the database file manually if
its contents matter to you, and always before applying migrations.

Merging a pull request that adds an Alembic migration does not apply it to
your `radar.db`. Apply it from the repository root, after a backup:

```bash
cp radar.db "radar.db.bak-$(date +%Y%m%d%H%M%S)"
set -a && source .env && set +a
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
```

The services do not migrate the database on startup.

## Rebuilding images

Rebuild the Docker images with `scripts/rebuild.sh`, not
`docker compose up --build`:

```
scripts/rebuild.sh                  # every service
scripts/rebuild.sh radar-dashboard  # one service
```

It runs `docker compose build --pull --no-cache` then `docker compose up -d`.
`radar-audit` (a `cli`-profile service) is rebuilt too but not started, since
it is a CLI run on demand rather than a long-running service.
Each Dockerfile upgrades its system packages (`apt-get upgrade` /
`apk upgrade`), but Docker reuses that step from its build cache as long as
the Dockerfile does not change, so security fixes published since the first
build never reach the image. `--pull` refreshes the base images and
`--no-cache` reruns every step, at the cost of a slower rebuild (dependencies
are reinstalled).

## Error tracking

Sentry is optional and disabled unless a DSN is set (see `.env.example`).
`SENTRY_BACKEND_DSN` is shared by `radar-api` and the `radar-audit` CLI;
`SENTRY_FRONTEND_DSN` is baked into the `radar-dashboard` bundle at image
build time, so changing it requires a rebuild. `radar-audit` only reports
unexpected crashes: tool failures and handled CLI errors are never sent.
No user data, headers, bodies, query strings or stack-frame variables are
collected.

In Docker, Compose passes `SENTRY_BACKEND_DSN` to `radar-api` and
`radar-audit` as `SENTRY_DSN`, the variable the code reads. A local
`uv run radar-audit` only reports to Sentry if `SENTRY_DSN` itself is
exported in the shell: sourcing `.env` sets `SENTRY_BACKEND_DSN`, not
`SENTRY_DSN`.

## Logging

`radar-api` and `radar-audit` write **structured logs** with structlog: each line is one event with named fields, written to **stderr** (stdout stays reserved for the CLI's own output, such as `--dry-run` plans and reports).

- **Format**: JSON lines in Docker or any non-terminal output, readable colored text in a terminal. Force one with `RADAR_LOG_FORMAT=json` or `RADAR_LOG_FORMAT=console`.
- **Level**: `RADAR_LOG_LEVEL` (`debug`, `info`, `warning`, `error`), `info` by default.
- **Never logged**: query strings, headers (the API key travels in one), request bodies.

| Event | Emitted by | Fields |
|---|---|---|
| `request_handled` | radar-api, one per HTTP request (error level for 5xx) | `method`, `path`, `status`, `duration_ms` |
| `audit_started` | radar-audit `run` | `repo`, `subprojects` |
| `tool_finished` | radar-audit, one per tool run | `tool`, `subproject`, `exit_code`, `duration_ms`, `audit_id` |
| `tool_crashed` | radar-audit, error level, when a tool raises | `tool`, `target`, `error`, `audit_id` |
| `audit_finished` | radar-audit `run` | `repo`, `tools_run`, `duration_ms`, `audit_id` |
| `scoring_finished` | radar-audit `score` | `repo`, `global_score`, `findings`, `audit_id` |

Every line logged during one audit carries its `audit_id`, so a whole audit can be isolated. Every line also has `timestamp` (UTC, ISO 8601) and `level`.

Reading them locally:

```bash
docker compose logs -f radar-api
# only server errors, as compact JSON:
docker compose logs --no-log-prefix radar-api | jq -c 'select(.level == "error")'
# the slowest tools of an audit run in a terminal:
RADAR_LOG_FORMAT=json uv run radar-audit run some-repo 2>&1 >/dev/null \
  | jq -s 'map(select(.event == "tool_finished")) | sort_by(-.duration_ms) | .[:5]'
```

**Logs and Sentry are complementary.** Sentry (above) collects *errors*: grouped exceptions, stack traces, alerts. Logs record *everything that happens*, including when nothing fails: durations, decisions, steps. When Sentry is enabled, the most recent log lines are attached to each error it reports as breadcrumbs. To search logs across days or build dashboards, see the [log aggregation guide](guides/log-aggregation.md) (Loki and Grafana, optional, not part of this project's stack).

## CI / automation

- `CHANGELOG.md` is regenerated primarily by a local `post-commit` hook wired into the `pre-commit` framework (`scripts/changelog-post-commit.sh`, runs git-cliff and folds the result into the same commit), so feature PRs already carry their own changelog entry
- As a fallback, [`.github/workflows/changelog.yml`](../.github/workflows/changelog.yml) still regenerates `CHANGELOG.md` on every push to `main` and opens a pull request (does not push directly to `main`), in case a commit lands without going through the local hook
- Pre-commit hooks run locally on every commit: `ruff`, `ruff-format` and `mypy` per Python package, and the dashboard's lint, format and type checks
- CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs on every push and pull request to `main`: the tests of every package with an 80% coverage gate, the dashboard's lint, format and type checks, and its Playwright end-to-end tests. The Python lint and type checks run only in pre-commit. Details in the [developer guide](guides/developer_guide.md#ci-pipeline) and [`CONTRIBUTING.md`](../CONTRIBUTING.md)

## Secrets

The audit engine reads local repositories read-only and does not require
any credentials or API keys for its current scope. If a future criterion
needs network access or an API key, it must be opt-in and explicitly
flagged (see the network-access decision in [`docs/adr/`](adr/)).
