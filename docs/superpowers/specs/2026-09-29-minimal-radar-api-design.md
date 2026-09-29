# radar-api — Minimal FastAPI service — Design

Status: draft, pending review.

Context: Phase 4, "Reporting and publication pipeline" (see
`docs/work-in-progress/reporting-pipeline-notes.md`), item C / increment
3.3. Depends loosely on increment 3.1 (report contract v2, merged main
via PR #57) and increment 3.2 (`Recommendation` population, merged main).
Reference: `docs/system-design.md` originally proposed `radar-api`
(FastAPI) + SQLite + `docker compose up` at Phase 0. This is that
proposal's first real implementation, scoped minimal: no broad CRUD, no
multi-user auth, no dashboard-specific endpoints beyond what the badge
(item D) and the future dashboard (item E) need to read.

Classified **architectural**: new top-level component (`radar-api/`)
alongside `radar-core/` and `radar-audit/` in the `uv` workspace, a new
service boundary that did not exist before.

## 1. Scope

Build a minimal `radar-api`: read endpoints over the existing data model
(repositories, audits, scores, findings, recommendations, roadmap items),
plus exactly 3 narrow, human-confirmed-only write endpoints. No broad
CRUD surface. This is what allows all report/finding/recommendation data
to be hosted by Radar itself and never written into an audited repo, a
hard constraint confirmed during the 2026-09-25 roadmap-planning session.

Explicitly out of scope for this increment:
- Multi-user authentication (email/password + token). A single static API
  key is sufficient today, since the software is effectively single-user
  (whoever controls the audited repos). Revisit if/when multi-user access
  is actually needed.
- The badge image rendering itself (item D) and the dashboard UI (item
  E) — this increment only needs to expose the data those will consume.
- Any endpoint outside the read/write list in section 3.

## 2. Project structure and components

New `uv` workspace member, alongside `radar-core` and `radar-audit`:

```
radar-api/
├── pyproject.toml
├── src/
│   └── radar_api/
│       ├── __init__.py
│       ├── main.py          # FastAPI app instantiation, router mounting
│       ├── config.py        # reads RADAR_DATABASE_URL, RADAR_API_KEY (no implicit default)
│       ├── dependencies.py  # FastAPI dependencies: DB session, API key check
│       ├── auth.py          # API key verification logic
│       ├── schemas/         # Pydantic request/response models (read + write)
│       └── routers/
│           ├── repositories.py   # list, detail, report, badge
│           ├── findings.py       # list + the 2 finding write endpoints
│           └── roadmap.py        # list + the roadmap-item write endpoint
└── tests/
    ├── conftest.py          # modeled on radar-audit's: temp DB, Alembic migrations, TestClient
    └── test_*.py            # one test file per router, plus test_auth.py
```

`pyproject.toml` is modeled on `radar-audit/pyproject.toml`: depends on
`radar-core` via `[tool.uv.sources]` workspace reference, adds `fastapi`
and `uvicorn` as runtime dependencies, `httpx` as a dev dependency (for
FastAPI's `TestClient`). Entry point via
`uvicorn radar_api.main:app` (see section 6 for how this is invoked in
Docker).

`main.py` stays thin: creates the FastAPI app, includes routers, no
business logic. Each router maps to one group of endpoints from section 3
(`repositories`, `findings`, `roadmap`), not a generic passthrough CRUD
router. `Score` and `Recommendation` data have no standalone endpoints of
their own — they are nested inside `GET /repositories/{id}/report`.

`config.py` mirrors `radar_audit.cli._database_url()`'s convention:
`RADAR_DATABASE_URL` is required, with an explicit error raised at
startup if unset — `radar-api` never assumes a default DB path, same as
`radar-audit`. `RADAR_API_KEY` follows the same convention.

The DB session is opened and closed per request through a FastAPI
dependency (`Depends(get_db_session)`) built on
`radar_core.db.get_engine`/`get_session`. No shared global session.

## 3. Endpoints and data flow

### Read endpoints

| Endpoint | Description |
|---|---|
| `GET /repositories` | list of repositories, each with its most recent global score (or "not yet audited") |
| `GET /repositories/{id}` | repository detail |
| `GET /repositories/{id}/report` | latest full report: scores per category/criterion (three-state model: scored / N/A with reason / not yet audited), findings, and their recommendations |
| `GET /repositories/{id}/findings` | list of findings, filterable by `status` and `severity` query params |
| `GET /repositories/{id}/badge` | JSON payload in shields.io endpoint-badge shape (`label`/`message`/`color`), derived from the latest global score — feeds item D |
| `GET /repositories/{id}/roadmap` | list of `RoadmapItem` rows and their status |

### Write endpoints (3, confirmed; require the API key; never transition automatically)

| Endpoint | Description |
|---|---|
| `PATCH /findings/{id}/verdict` | updates `Finding.human_verdict` (UNREVIEWED -> TRUE_POSITIVE/FALSE_POSITIVE) |
| `PATCH /findings/{id}/status` | updates `Finding.status` (OPEN -> RESOLVED/WONT_FIX) |
| `PATCH /roadmap-items/{id}/status` | updates `RoadmapItem.status`; transitioning to `DONE` requires an explicit `done_evidence_id` in the request body (see section 4) |

### Data flow

Each endpoint opens a short-lived DB session via the
`Depends(get_db_session)` dependency, runs a direct SQLModel `select()`
against the existing `radar-core` models, serializes the result into a
Pydantic response schema, and closes the session. No intermediate
service layer, no caching: internal audit-tooling traffic volume does
not justify either. Read schemas (`schemas/*.py`) are flat projections
of the SQLModel models, not raw pass-throughs, so internal-only fields
(e.g. `ToolResult.raw_output`) are never exposed.

## 4. Authentication

A static API key, confirmed during brainstorming (no email/password +
token account system for this increment; revisit only if multi-user
access is actually needed later).

- **Storage:** `RADAR_API_KEY` environment variable, read once at
  startup, following the same required-no-default convention as
  `RADAR_DATABASE_URL`; the app fails to start if it's unset.
- **Verification:** `X-API-Key` request header, checked by a
  `require_api_key` FastAPI dependency using `secrets.compare_digest`
  (constant-time comparison).
- **Scope:** applied only to the 3 write endpoints in section 3. Read
  endpoints stay open, since they feed the public badge and (later) an
  unauthenticated dashboard.
- **Failure:** missing or invalid key returns `401 Unauthorized` with a
  generic `{"detail": "invalid or missing API key"}` body, no further
  detail (avoids helping brute-force attempts).
- **No key rotation or multiple scopes** in this increment: one key, one
  access level (write). YAGNI while there is a single human operator.

## 5. Error handling and business rules

- **Resource not found** (`repository`, `finding`, `roadmap-item` id does
  not exist): `404 Not Found`, standard FastAPI `HTTPException` JSON
  body.
- **Payload validation** (e.g. a `status` value outside the enum, a
  missing `done_evidence_id` when the target is `DONE`): `422
  Unprocessable Entity`, generated automatically by Pydantic request
  schema validation. No redundant manual validation.
- **"Never auto-DONE" constraint:** the Pydantic request schema for
  `PATCH /roadmap-items/{id}/status` uses a `model_validator` that makes
  `done_evidence_id` mandatory whenever `status == DONE`. The API
  structurally refuses the transition without evidence, rather than
  relying on a downstream business check.
- **Invalid status transitions** (e.g. `RESOLVED -> RESOLVED`, or a value
  not defined by `FindingStatus`/`HumanVerdict`/`RoadmapStatus`): `400
  Bad Request` with the rejected transition in the detail. The existing
  `radar_core.enums` definitions are the source of truth for valid
  values; the API checks the target value is a defined enum member and
  differs from the current value — it does not reimplement a state
  machine.
- **Unhandled errors** (internal bug, DB unavailable): left to propagate
  as FastAPI's default `500`, no generic catch-all handler that would
  mask the underlying error — consistent with the rest of the monorepo's
  error-handling posture.

## 6. Deployment

No `Dockerfile` or `docker-compose.yml` exists yet in the repo; both are
new for this increment.

`radar-api/Dockerfile`: Python 3.12 slim image, installs the `uv`
workspace (`radar-core` + `radar-api`), runs
`uvicorn radar_api.main:app --host 0.0.0.0 --port 8000`.

`docker-compose.yml` at the repo root (new file). Confirmed scope:
`radar-api` and `radar-audit` containerized now, `radar-dashboard`
reserved as a placeholder (commented out, not built yet):

```yaml
services:
  radar-api:
    build: ./radar-api
    environment:
      - RADAR_DATABASE_URL=sqlite:////data/radar.db
      - RADAR_API_KEY=${RADAR_API_KEY}
    volumes:
      - radar-data:/data
    ports:
      - "8000:8000"

  radar-audit:
    build: ./radar-audit
    environment:
      - RADAR_DATABASE_URL=sqlite:////data/radar.db
    volumes:
      - radar-data:/data
      - ${RADAR_PORTFOLIO_PATH}:/portfolio:ro
    profiles: ["cli"]   # invoked on demand (docker compose run), not started with `up`

  # radar-dashboard:
  #   reserved for item E (Vue 3 + Vite SPA) -- not built yet

volumes:
  radar-data:
```

`radar-audit` uses `profiles: ["cli"]` because it is invoked on demand
(`docker compose run radar-audit ...`), not a long-running service like
`radar-api`; this keeps it from starting unnecessarily on every
`docker compose up`. Both services share the `radar-data` volume; SQLite
runs in WAL mode (confirmed during brainstorming), which allows
`radar-api`'s continuous reads and `radar-audit`'s occasional writes to
coexist on the same file as long as both run on the same host/volume.
`radar-dashboard` stays commented out rather than as an active empty
entry, to avoid a service pointing at a nonexistent directory; it will be
uncommented and completed when item E is built.

## 7. Testing strategy

Same approach as `radar-audit`: `pytest` + FastAPI's `TestClient` (via
`httpx`), strict TDD.

- `tests/conftest.py`: a `db_session` fixture modeled on `radar-audit`'s
  (temporary SQLite DB, Alembic migrations applied via
  `RADAR_DATABASE_URL`), plus a `client` fixture that builds a
  `TestClient(app)` with the `get_db_session` dependency overridden
  (`app.dependency_overrides`) to reuse the same test session, avoiding
  any dependency on a real running DB process.
- One test file per router, mirroring the `routers/` structure
  (`test_repositories.py`, `test_findings.py`, `test_roadmap.py`). Each
  covers the happy path, `404` for a missing resource, `422` for invalid
  payloads, and, for the 3 write endpoints specifically: `401` without
  an API key, `400` for an invalid transition, and the structural
  rejection of `DONE` without `done_evidence_id`.
- `test_auth.py`: tests `require_api_key` in isolation (missing key,
  wrong key, correct key), independent of the routers that use it.
- No Docker-based end-to-end test in this increment: the `pytest` suite
  is sufficient to validate the API's behavior; `docker-compose.yml` is
  verified manually (`docker compose up`) rather than through an
  automated suite, consistent with the monorepo's current CI tooling
  level.
