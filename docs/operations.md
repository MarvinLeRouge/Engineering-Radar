[🇫🇷 Version française](operations.fr.md) | 🇬🇧 English version

---

# Operations

Minimal operations reference. This is a local, single-user, offline-first
system: there is no hosted deployment yet.

## Running the audit engine

`radar-audit` is invoked manually as a CLI command; it is not a
long-running service. See the [developer guide](guides/developer_guide.md)
for setup and usage.

## Data

All structured audit data lives in the database pointed to by
`RADAR_DATABASE_URL`. For local use this is typically a gitignored SQLite
file; nothing about the schema assumes SQLite specifically (managed via
Alembic migrations in `radar-core`).

Raw tool output captured during a run is kept alongside the normalized
results rather than discarded, so a finding can always be traced back to
the tool invocation that produced it.

There is no backup automation yet: back up the database file manually if
its contents matter to you (for example before running a destructive
migration).

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
- There is no CI pipeline yet running tests or the `ruff`/`mypy` gates remotely; these run locally via pre-commit hooks (see [`CONTRIBUTING.md`](../CONTRIBUTING.md)). Tracked in [`docs/roadmap.md`](roadmap.md)

## Secrets

The audit engine reads local repositories read-only and does not require
any credentials or API keys for its current scope. If a future criterion
needs network access or an API key, it must be opt-in and explicitly
flagged (see the network-access decision in [`docs/adr/`](adr/)).
