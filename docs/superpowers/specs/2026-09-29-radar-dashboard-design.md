# radar-dashboard — Vue 3 + Vite SPA — Design

Status: draft, pending review.

Context: Phase 4, "Reporting and publication pipeline" (see
`docs/work-in-progress/reporting-pipeline-notes.md`), item E / increment
3.5. Depends on increment 3.3 (`radar-api`, merged main via PR #64) and
loosely on increment 3.4 (quality badge, merged main via PR #65/#66) —
not a hard technical dependency, but the dashboard and the badge should
present consistent numbers. Reference: `docs/system-design.md` originally
proposed a local dashboard at Phase 0; this is that proposal's first real
implementation.

Classified **architectural**: new top-level component
(`radar-dashboard/`), a Node/Vue project outside the `uv` workspace that
did not exist before, consuming `radar-api` as its only data source.

## 1. Scope

Build `radar-dashboard`: a read-focused SPA over `radar-api`'s data
(repository list, per-repository report, roadmap), plus the three
human-confirmed write actions `radar-api` already exposes (finding
verdict, finding status, roadmap item status). No new business logic —
every write goes straight to an existing `radar-api` `PATCH` endpoint.

Two visual requirements are already frozen by
`reporting-pipeline-notes.md` and drive section 4 below:
- Score gauges render as discrete flat-color bands, not a continuous
  gradient — this is meant to read as professional tooling, not a toy.
- `not_applicable` and `not_yet_audited` criteria are visually distinct
  (two different grays) with the reason available on demand, never just
  a silently missing number.

This increment also makes two narrow, confirmed additions to `radar-api`
(sections 3 and 5), discovered while designing the roadmap screen and the
"mark as done" flow:
- `GET /roadmap-items/{id}/evidence-candidates` — a new read endpoint.
- `RoadmapItemRead` gains `title` and `description` (from the linked
  `ImprovementTask`) — an additive change to an existing endpoint, no new
  endpoint.

Both stay within `radar-api`'s existing "narrow, read-heavy, no broad
CRUD" posture (section 1 of the `radar-api` spec) — they are read-only
projections of data the write endpoints already validate against, not new
write surface.

Explicitly out of scope for this increment:
- Charting library. Confirmed unnecessary: bands are discrete/flat, not
  continuous gradients or trend lines, so plain SVG/CSS renders them
  directly. Revisit only at Phase 7, when score-stability trend lines
  across re-audits are actually scoped — `docs/toolchain.md` records this
  as an explicit deferral, not an oversight.
- E2E tests (same posture as `radar-api`: `pytest`/`vitest` unit and
  component tests are sufficient for this increment; Docker Compose
  wiring is verified manually).
- A backend-side account/session system for the API key — see section 5.
- Multi-repository comparison views, portfolio-wide rollups (Phase 5/6
  concerns, not this SPA).

## 2. Project structure and components

New top-level directory, outside the `uv` workspace (Node/TypeScript, not
Python), matching Triton's frontend socle for stack consistency:

```
radar-dashboard/
├── package.json          # Vue 3, Vite, TypeScript, Pinia, Vue Router
├── vite.config.ts        # dev-server proxy: /api -> http://localhost:8000
├── nginx.conf            # SPA fallback (try_files ... /index.html)
├── Dockerfile             # multi-stage: node build -> nginx:alpine
└── src/
    ├── main.ts
    ├── App.vue
    ├── router/
    │   └── index.ts               # routes: "/", "/repositories/:id", "/settings"
    ├── stores/
    │   ├── apiKey.ts               # sessionStorage-backed API key (section 5)
    │   ├── repositories.ts         # repository list + selected report
    │   └── __tests__/
    ├── api/
    │   └── client.ts               # thin fetch wrapper, relative /api/... paths
    ├── components/
    │   ├── ScoreGauge.vue          # flat-band gauge, section 4
    │   ├── FindingCard.vue         # severity badge + recommendation text
    │   ├── RoadmapItemRow.vue      # title/description/status + DONE action
    │   ├── EvidencePicker.vue      # evidence-candidates dropdown, section 5
    │   └── __tests__/
    └── views/
        ├── RepositoryListView.vue  # "/"
        ├── RepositoryDetailView.vue# "/repositories/:id"
        ├── SettingsView.vue        # "/settings"
        └── __tests__/
```

`package.json` mirrors Triton's `frontend/package.json`: Vue 3 + Pinia as
runtime dependencies; Vite, TypeScript, ESLint (`eslint-plugin-vue`,
`eslint-plugin-oxlint`, `eslint-config-prettier`), Prettier, Vitest,
`@vue/test-utils`, `jsdom` as dev dependencies. `vue-router` is added on
top of Triton's exact dependency set — Triton is single-view and has no
router; this SPA needs one for the repository-list / repository-detail /
settings navigation.

`src/api/client.ts` is the single place that knows about `radar-api`'s
shapes: one function per endpoint (`listRepositories`,
`getRepositoryReport`, `getRepositoryRoadmap`,
`getRoadmapItemEvidenceCandidates`, `updateFindingVerdict`,
`updateFindingStatus`, `updateRoadmapItemStatus`), each typed against a
TypeScript interface matching the corresponding `radar-api` Pydantic
schema. No generated client, no OpenAPI codegen — the endpoint surface is
small and stable enough that hand-written types are simpler to read and
maintain than adding a codegen step.

Pinia stores hold fetched data and loading/error state; components stay
presentational. `stores/repositories.ts` exposes actions
(`fetchList`, `fetchReport(id)`, `fetchRoadmap(id)`) and getters; views
call actions on mount, components render store state via props.

## 3. Screens and data flow

### Communication with the API — same-origin, no CORS

Rather than call `radar-api.marvinlerouge.dev` cross-origin (which would
require configuring CORS on `radar-api`), this reuses the pattern already
in production on Triton: same origin, `radar.marvinlerouge.dev/api/*`
routed by Traefik to the existing `radar-api` container with the `/api`
prefix stripped (see section 7 for the exact labels). The dashboard's API
client only ever calls relative paths (`/api/repositories`, ...). In
local development, Vite's dev-server proxy (`vite.config.ts`) performs
the same rewrite to `http://localhost:8000`, so no Traefik is needed to
develop the SPA locally.

### Screens

| Route | Purpose |
|---|---|
| `/` | Repository list: name, most recent global score, audit status (reuses `GET /repositories`) |
| `/repositories/:id` | Repository detail: categories -> criteria -> findings with recommendations (`GET /repositories/{id}/report`), plus a roadmap tab (`GET /repositories/{id}/roadmap`) |
| `/settings` | API key entry, stored in `sessionStorage` (section 5) |

### Data flow

Each view's `onMounted` hook triggers a store action, which calls
`api/client.ts`, which issues a relative-path `fetch`. Responses populate
the store; the view renders loading/error/data states directly from
store getters. No client-side caching layer beyond what the Pinia store
already holds in memory for the current session — traffic volume and
data freshness needs don't justify one, consistent with `radar-api`'s own
"no caching" stance.

## 4. Score gauges and visual design

Gauges render as five discrete flat-color bands, reusing the exact
thresholds `radar-api`'s `_badge_color()` already uses server-side (`>=8`
brightgreen, `>=6` green, `>=4` yellow, `>=2` orange, else red), so the
badge (item D) and the dashboard always agree on what a given score
means. `ScoreGauge.vue` takes a `value: number | null` and a `status:
"scored" | "not_applicable" | "not_yet_audited"` prop (matching
`CriterionReport`/`CategoryReport`'s `status` field verbatim — category
reports only ever use `"scored"`/`"not_yet_audited"`, criterion reports
use all three) and picks the band from `value` when `status === "scored"`.

`not_applicable` and `not_yet_audited` render as two visually distinct
grays (not the same shade), with no numeric band. The reason
(`na_reason` for `not_applicable`, or the fixed string "not yet audited"
for `not_yet_audited`) is exposed both on hover (`title` attribute) and
on click (a small popover/tooltip toggled on tap), so the information is
reachable on touch devices, not just with a mouse.

Findings render with a severity badge using `FindingSeverity`'s existing
5-tier vocabulary (CRITICAL/HIGH/MEDIUM/LOW/INFO) and a fixed color per
tier — a separate, smaller palette from the 0-10 score bands above (the
two encode different things: a finding's severity is not a score). No
new severity vocabulary, per `reporting-pipeline-notes.md`.

No charting library (see section 1) — `ScoreGauge.vue` and the severity
badges are plain SVG/CSS: a fixed set of colored segments/labels, not a
generated chart.

## 5. Write actions and authentication

### API key handling

`radar-api`'s three write endpoints require a static `X-API-Key` header
(see the `radar-api` spec, section 4). The dashboard has no backend of
its own and no account system — the `/settings` view lets the operator
paste the key, held in `sessionStorage` only (cleared when the tab
closes, never persisted to `localStorage`, never sent anywhere except as
the `X-API-Key` header on the three `PATCH` calls, never committed to
source). `stores/apiKey.ts` wraps this: a getter/setter pair over
`sessionStorage`, consumed by `api/client.ts` when building write
requests. Read requests never send the header.

If a write request returns `401` (missing/invalid key), the UI surfaces
an inline error directing the operator back to `/settings` — no retry
loop, no silent failure.

### Finding verdict and status

`FindingCard.vue` exposes simple controls (a verdict selector, a status
selector) that call `updateFindingVerdict`/`updateFindingStatus`
directly — thin wrappers around the existing `PATCH` endpoints, no new
business logic on the frontend.

### Roadmap item status, and the `DONE` evidence requirement

`radar-api`'s `PATCH /roadmap-items/{id}/status` structurally requires a
`done_evidence_id` when transitioning to `DONE` (its request schema's
`model_validator` rejects `DONE` without one). Until now nothing exposed
which `Evidence` rows are valid for a given roadmap item, which would
have forced the operator to know an internal database ID by hand.

**New `radar-api` endpoint:** `GET /roadmap-items/{id}/evidence-candidates`
— returns exactly the `Evidence` rows the existing `PATCH` already
accepts for that roadmap item: rows whose `finding_id` belongs to a
`Finding` linked (via `FindingImprovementTaskLink`) to the roadmap item's
`improvement_task_id`. Same linking query the router
(`update_roadmap_item_status`) already runs server-side to validate
`done_evidence_id` — this endpoint exposes it as a read, rather than
duplicating or loosening that check.

```python
class EvidenceCandidate(BaseModel):
    id: int
    finding_id: int
    evidence_type: str
    content: str
    created_at: datetime
```

`RoadmapItemRow.vue`'s "mark as done" action fetches this list and
renders it as a picker (`EvidencePicker.vue`: evidence type + a truncated
preview of `content`), so the operator selects evidence instead of typing
a raw ID. Selecting one and confirming calls
`updateRoadmapItemStatus(id, { status: "DONE", done_evidence_id })`.
Other status transitions (`TODO`, `IN_PROGRESS`, `WONT_FIX`) skip the
picker and call the same endpoint with `done_evidence_id` omitted.

**`RoadmapItemRead` extension:** the schema currently exposes only
`improvement_task_id`, not the task's `title`/`description` — without
them, the roadmap tab would show bare numeric IDs. This adds two
required fields, sourced from the already-joined `ImprovementTask` row:

```python
class RoadmapItemRead(BaseModel):
    id: int
    improvement_task_id: int
    title: str
    description: str
    status: str
    priority: int
    estimated_effort: str | None
    estimated_impact: str | None
    promoted_at: datetime
    done_at: datetime | None
```

Purely additive to an existing endpoint (`GET
/repositories/{id}/roadmap`) — no new endpoint, no breaking change to the
existing shape.

## 6. Testing strategy

Vitest + `@vue/test-utils`, mirroring Triton's `frontend` setup
(`test:unit` -> `vitest`). Tests live in `__tests__/` folders colocated
with the code they cover (`stores/__tests__/`, `components/__tests__/`,
`views/__tests__/`), matching Triton's layout.

- `api/client.ts` is stubbed manually in store and component tests (a
  hand-written fake implementing the same function signatures) — no new
  dependency such as `msw`, consistent with keeping the dependency set as
  small as `radar-api`'s own test setup.
- Store tests (`stores/__tests__/repositories.spec.ts`, etc.): actions
  update state correctly on success, and set an error state on a
  rejected fetch/write.
- Component tests: `ScoreGauge.vue` renders the correct band for each
  score range and the correct gray + reason for `not_applicable`/
  `not_yet_audited`; `FindingCard.vue` renders the right severity badge
  and calls the right client function on each control's change event;
  `RoadmapItemRow.vue` shows the evidence picker only when transitioning
  to `DONE`, and calls `updateRoadmapItemStatus` with `done_evidence_id`
  omitted for every other target status.
- View tests: mount each view with a stubbed store, assert loading/error/
  data states render correctly.
- No E2E suite this increment (see section 1); the Docker Compose /
  Traefik wiring in section 7 is verified manually
  (`docker compose up`), consistent with `radar-api`'s current posture.

On the `radar-api` side, the two additions from section 5 follow that
project's existing TDD pattern: a new
`radar-api/tests/test_roadmap.py` case for
`GET /roadmap-items/{id}/evidence-candidates` (happy path, `404` for a
missing roadmap item, empty list when no evidence is linked), and an
update to the existing `RoadmapItemRead` tests to assert `title`/
`description` are present.

## 7. Deployment

`radar-dashboard/Dockerfile`: multi-stage, Node build -> static `nginx`
image, copying `dist/` into `nginx:alpine` — identical shape to
`Triton/frontend/Dockerfile`. `nginx.conf` is the same SPA-fallback
config as Triton's (`try_files $uri $uri/ /index.html`), with gzip
enabled for the usual static asset types.

`docker-compose.yml` at the repo root (existing file, extended): the
commented-out `radar-dashboard` placeholder is filled in, and `radar-api`
gains a second Traefik router for the `/api` prefix — same pattern as
Triton's backend (`PathPrefix` + `stripprefix` middleware):

```yaml
services:
  radar-api:
    # ... existing build/environment/volumes/ports unchanged ...
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      # existing direct-host router, unchanged
      - "traefik.http.routers.radar-api.rule=Host(`radar-api.marvinlerouge.local`)"
      - "traefik.http.routers.radar-api.entrypoints=web"
      - "traefik.http.services.radar-api.loadbalancer.server.port=8000"
      # new: /api/* on the dashboard's host, prefix stripped
      - "traefik.http.routers.radar-api-proxied.rule=Host(`radar.marvinlerouge.local`) && PathPrefix(`/api`)"
      - "traefik.http.routers.radar-api-proxied.entrypoints=web"
      - "traefik.http.middlewares.radar-api-strip.stripprefix.prefixes=/api"
      - "traefik.http.routers.radar-api-proxied.middlewares=radar-api-strip"
      - "traefik.http.routers.radar-api-proxied.service=radar-api"

  radar-dashboard:
    build:
      context: .
      dockerfile: radar-dashboard/Dockerfile
    networks:
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.radar-dashboard.rule=Host(`radar.marvinlerouge.local`)"
      - "traefik.http.routers.radar-dashboard.entrypoints=web"
      - "traefik.http.services.radar-dashboard.loadbalancer.server.port=80"
```

`radar-api` keeps its existing direct host
(`radar-api.marvinlerouge.local`) for the badge (item D) and any direct
API access, and gains the `/api`-prefixed router scoped to the
dashboard's host — both routers point at the same underlying service, so
no duplicate container is needed. The production routers
(`radar.marvinlerouge.dev`, `websecure`/`letsencrypt`) are not wired in
this increment, matching `radar-api`'s own current state (no production
compose file yet).

## 8. Known follow-ups

- No charting library now (section 1); revisit only when Phase 7 scopes
  score-stability trend lines.
- No account/session system for the API key (section 5); the
  `sessionStorage` approach is appropriate for a single-operator tool and
  should be revisited only if multi-user access is ever needed — same
  posture `radar-api`'s own spec already takes on this question.
- Production Traefik routers (`.dev` host, `websecure`) are deferred
  until a production compose file exists for the project as a whole, not
  specific to this increment.
