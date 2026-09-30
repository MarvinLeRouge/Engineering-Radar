# radar-dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** stand up `radar-dashboard`, a Vue 3 + Vite SPA that reads `radar-api`'s data
(repositories, reports, roadmap) and drives its three human-confirmed write endpoints, plus two
narrow additive `radar-api` endpoints the dashboard needs (evidence candidates for the roadmap
"mark as done" flow, and roadmap item title/description).

**Architecture:** a new top-level Node/TypeScript project (`radar-dashboard/`, outside the `uv`
workspace) matching Triton's frontend socle: Vue 3 + Vite + TypeScript, Pinia stores for fetched
data and the session-scoped API key, Vue Router for the three screens, a single `api/client.ts`
module that is the only place aware of `radar-api`'s request/response shapes. Same-origin `/api/*`
calls only, proxied by Vite locally and by Traefik in Docker — no CORS handling anywhere in the
app. Score gauges are discrete flat-color bands (plain SVG/CSS, no charting library), reusing
`radar-api`'s `_badge_color()` thresholds server- and client-side.

**Tech Stack:** Vue 3.5, Vite 8, TypeScript ~6.0, Pinia ^3.0.4, Vue Router ^5.3.1, ESLint 10 +
`eslint-plugin-vue` + `eslint-plugin-oxlint` + `eslint-config-prettier`, Prettier 3.8.4, Vitest 4 +
`@vue/test-utils` + `jsdom`. Backend side: FastAPI/Pydantic additions to the existing `radar-api`
package (Python 3.12, SQLModel).

**Spec:** `docs/superpowers/specs/2026-09-29-radar-dashboard-design.md`

## Global Constraints

- `radar-dashboard/` is a new top-level directory, Node/TypeScript, **outside** the `uv` workspace.
- Stack pinned to: `vue@^3.5.38`, `vite@^8.0.16`, `typescript@~6.0.0`, `pinia@^3.0.4`,
  `vue-router@^5.3.1`, `vitest@^4.1.9`, `@vue/test-utils@^2.4.11`, `jsdom@^29.1.1` (exact devDeps
  in Task 3).
- All API access goes through relative `/api/...` paths only — no absolute
  `radar-api.marvinlerouge.*` URL anywhere in the app, no CORS handling.
- Score-band thresholds mirror `radar-api`'s `_badge_color()` exactly: `>=8` brightgreen, `>=6`
  green, `>=4` yellow, `>=2` orange, else red.
- `not_applicable` and `not_yet_audited` render as two visually distinct grays, with the reason
  available on hover (`title` attribute) **and** on click (touch-reachable).
- The API key lives only in `sessionStorage`, is sent only as the `X-API-Key` header on the three
  `PATCH` calls, and is never sent on read requests or persisted to `localStorage`.
- No charting library. No E2E test suite this increment.
- `radar-api`'s two additions (Tasks 1-2) stay read-only and reuse the same linked-finding-ids
  check `update_roadmap_item_status` already runs — no loosening of that validation.

## Review Focus

1. A criterion report with `status: "not_applicable"` and `value: null` must render the NA gray
   band with its reason, not crash or misrender by trying to pick a color band from a null value.
2. A roadmap status update to any target other than `DONE` must omit `done_evidence_id` from the
   request body entirely (not send it as `null`) — matching what `radar-api`'s Pydantic schema
   expects for a non-DONE transition.
3. The repository list and detail views must render a distinguishable loading state and error
   state (not a blank page or an unhandled rejection) when a fetch is in flight or fails.
4. A write request that returns `401` (missing/invalid API key) must surface an inline message
   pointing at Settings, not fail silently or throw an unhandled promise rejection.
5. The evidence picker must handle an empty evidence-candidates list gracefully (message, not a
   picker with nothing to select) — a roadmap item can be `IN_PROGRESS` with no evidence yet.

---

### Task 1: `radar-api` — `GET /roadmap-items/{id}/evidence-candidates`

**Files:**
- Modify: `radar-api/src/radar_api/schemas/roadmap.py`
- Modify: `radar-api/src/radar_api/routers/roadmap.py`
- Modify: `radar-api/tests/test_roadmap.py`

**Interfaces:**
- Consumes: existing `radar_api.dependencies.get_db_session`, existing
  `radar_api.routers.roadmap._to_roadmap_item_read`
- Produces: `radar_api.schemas.roadmap.EvidenceCandidate`,
  `radar_api.routers.roadmap._linked_finding_ids(session, improvement_task_id) -> set[int]` (a
  helper extracted from the existing `update_roadmap_item_status` DONE-branch and reused by the
  new endpoint — the two now share one definition of "which evidence is valid for this roadmap
  item" instead of the check living only inline in the `PATCH` handler)

**Design note:** `radar-api/src/radar_api/routers/roadmap.py` currently computes
`linked_finding_ids` inline inside `update_roadmap_item_status`'s `DONE` branch. This task pulls
that into a named helper so the new endpoint returns exactly what the existing `PATCH` already
accepts, rather than re-deriving the rule a second time.

- [ ] **Step 1: Write the failing tests**

Append to `radar-api/tests/test_roadmap.py`:

```python
def test_evidence_candidates_returns_404_when_roadmap_item_missing(client):
    response = client.get("/roadmap-items/999/evidence-candidates")

    assert response.status_code == 404


def test_evidence_candidates_returns_empty_list_when_none_linked(client, db_session):
    repo = _make_repository(db_session, "repo-evidence-empty")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
    assert response.json() == []


def test_evidence_candidates_returns_evidence_linked_via_finding(client, db_session):
    repo = _make_repository(db_session, "repo-evidence")
    finding = _make_finding_chain(db_session, repo)
    evidence = _make_evidence(db_session, finding)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == evidence.id
    assert body[0]["finding_id"] == finding.id
    assert body[0]["evidence_type"] == "HUMAN_CONFIRMATION"
    assert body[0]["content"] == "fixed in PR #123"


def test_evidence_candidates_excludes_evidence_from_unrelated_finding(client, db_session):
    repo = _make_repository(db_session, "repo-evidence-unrelated")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    other_repo = _make_repository(db_session, "repo-evidence-unrelated-other")
    other_finding = _make_finding_chain(db_session, other_repo)
    _make_evidence(db_session, other_finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
    assert response.json() == []


def test_evidence_candidates_no_api_key_required(client, db_session):
    repo = _make_repository(db_session, "repo-evidence-no-auth")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.get(f"/roadmap-items/{roadmap_item.id}/evidence-candidates")

    assert response.status_code == 200
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v -k evidence_candidates`
Expected: FAIL (`404 Not Found` on a route that does not exist yet, since FastAPI's default 404
applies to unmatched routes too — the collection succeeds but every new test fails on the
assertion)

- [ ] **Step 3: Add the schema**

Add to `radar-api/src/radar_api/schemas/roadmap.py` (new import at the top, new class at the
bottom):

```python
from datetime import datetime
```

```python
class EvidenceCandidate(BaseModel):
    id: int
    finding_id: int
    evidence_type: str
    content: str
    created_at: datetime
```

- [ ] **Step 4: Extract the `_linked_finding_ids` helper and add the route**

Replace the inline `linked_finding_ids` computation inside `update_roadmap_item_status` and add
the new endpoint. `radar-api/src/radar_api/routers/roadmap.py` becomes:

```python
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from radar_core.enums import RoadmapStatus
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select

from radar_api.auth import require_api_key
from radar_api.dependencies import get_db_session
from radar_api.schemas.roadmap import EvidenceCandidate, RoadmapItemRead, RoadmapItemStatusUpdate

router = APIRouter(tags=["roadmap"])


def _to_roadmap_item_read(roadmap_item: RoadmapItem) -> RoadmapItemRead:
    assert roadmap_item.id is not None
    return RoadmapItemRead(
        id=roadmap_item.id,
        improvement_task_id=roadmap_item.improvement_task_id,
        status=roadmap_item.status.value,
        priority=roadmap_item.priority,
        estimated_effort=roadmap_item.estimated_effort,
        estimated_impact=roadmap_item.estimated_impact,
        promoted_at=roadmap_item.promoted_at,
        done_at=roadmap_item.done_at,
    )


def _linked_finding_ids(session: Session, improvement_task_id: int) -> set[int]:
    return set(
        session.exec(
            select(FindingImprovementTaskLink.finding_id).where(
                FindingImprovementTaskLink.improvement_task_id == improvement_task_id
            )
        ).all()
    )


@router.get("/repositories/{repository_id}/roadmap", response_model=list[RoadmapItemRead])
def list_roadmap_items(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[RoadmapItemRead]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    roadmap_items = session.exec(
        select(RoadmapItem)
        .join(ImprovementTask, ImprovementTask.id == RoadmapItem.improvement_task_id)  # type: ignore[arg-type]
        .join(
            FindingImprovementTaskLink,
            FindingImprovementTaskLink.improvement_task_id == ImprovementTask.id,  # type: ignore[arg-type]
        )
        .join(Finding, Finding.id == FindingImprovementTaskLink.finding_id)  # type: ignore[arg-type]
        .join(ScoringRun, ScoringRun.id == Finding.scoring_run_id)  # type: ignore[arg-type]
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .distinct()
    ).all()
    return [_to_roadmap_item_read(item) for item in roadmap_items]


@router.get(
    "/roadmap-items/{roadmap_item_id}/evidence-candidates",
    response_model=list[EvidenceCandidate],
)
def list_roadmap_item_evidence_candidates(
    roadmap_item_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[EvidenceCandidate]:
    roadmap_item = session.get(RoadmapItem, roadmap_item_id)
    if roadmap_item is None:
        raise HTTPException(status_code=404, detail="roadmap item not found")

    linked_finding_ids = _linked_finding_ids(session, roadmap_item.improvement_task_id)
    if not linked_finding_ids:
        return []

    evidence_rows = session.exec(
        select(Evidence).where(Evidence.finding_id.in_(linked_finding_ids))  # type: ignore[attr-defined]
    ).all()
    return [
        EvidenceCandidate(
            id=e.id,  # type: ignore[arg-type]
            finding_id=e.finding_id,  # type: ignore[arg-type]
            evidence_type=e.evidence_type.value,
            content=e.content,
            created_at=e.created_at,
        )
        for e in evidence_rows
    ]


@router.patch(
    "/roadmap-items/{roadmap_item_id}/status",
    response_model=RoadmapItemRead,
    dependencies=[Depends(require_api_key)],
)
def update_roadmap_item_status(
    roadmap_item_id: int,
    payload: RoadmapItemStatusUpdate,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> RoadmapItemRead:
    roadmap_item = session.get(RoadmapItem, roadmap_item_id)
    if roadmap_item is None:
        raise HTTPException(status_code=404, detail="roadmap item not found")
    if roadmap_item.status == payload.status:
        raise HTTPException(
            status_code=400,
            detail=f"roadmap item already has status {payload.status.value}",
        )

    if payload.status == RoadmapStatus.DONE:
        evidence = session.get(Evidence, payload.done_evidence_id)
        if evidence is None:
            raise HTTPException(
                status_code=400,
                detail="done_evidence_id does not reference an existing evidence row",
            )
        linked_finding_ids = _linked_finding_ids(session, roadmap_item.improvement_task_id)
        if evidence.finding_id not in linked_finding_ids:
            raise HTTPException(
                status_code=400,
                detail="done_evidence_id does not belong to a finding linked to this roadmap item",
            )
        roadmap_item.done_evidence_id = payload.done_evidence_id
        roadmap_item.done_at = datetime.now(UTC)
    else:
        roadmap_item.done_evidence_id = None
        roadmap_item.done_at = None

    roadmap_item.status = payload.status
    session.add(roadmap_item)
    session.commit()
    session.refresh(roadmap_item)
    return _to_roadmap_item_read(roadmap_item)
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v`
Expected: PASS (15 tests total: 10 existing + 5 new)

- [ ] **Step 6: Commit**

```bash
git add radar-api/src/radar_api/schemas/roadmap.py radar-api/src/radar_api/routers/roadmap.py radar-api/tests/test_roadmap.py
git commit -m "feat(radar-api): add GET /roadmap-items/{id}/evidence-candidates"
```

---

### Task 2: `radar-api` — `RoadmapItemRead` gains `title`/`description`

**Files:**
- Modify: `radar-api/src/radar_api/schemas/roadmap.py`
- Modify: `radar-api/src/radar_api/routers/roadmap.py`
- Modify: `radar-api/tests/test_roadmap.py`

**Interfaces:**
- Consumes: `ImprovementTask.title: str`, `ImprovementTask.description: str` (existing
  `radar-core` fields, already joined by `list_roadmap_items`'s query but not currently selected)
- Produces: `RoadmapItemRead.title: str`, `RoadmapItemRead.description: str` (both required —
  `ImprovementTask.title`/`.description` are non-nullable columns)

**Design note:** `list_roadmap_items`'s query already joins `ImprovementTask` (needed for the
`FindingImprovementTaskLink` chain) but only selects `RoadmapItem` columns. Selecting the tuple
`(RoadmapItem, ImprovementTask)` instead avoids an extra per-row query.

- [ ] **Step 1: Write the failing test**

Append to `radar-api/tests/test_roadmap.py`:

```python
def test_list_roadmap_items_includes_task_title_and_description(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap-title")
    finding = _make_finding_chain(db_session, repo)
    _make_roadmap_item(db_session, finding)

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["title"] == "Fix it"
    assert body[0]["description"] == "..."
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v -k title_and_description`
Expected: FAIL (`KeyError`/`AssertionError` — `title` is not a key in the current response body)

- [ ] **Step 3: Extend the schema**

Modify `radar-api/src/radar_api/schemas/roadmap.py`'s `RoadmapItemRead`:

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

- [ ] **Step 4: Update the query and the read-model builder**

Modify `radar-api/src/radar_api/routers/roadmap.py`:

```python
def _to_roadmap_item_read(
    roadmap_item: RoadmapItem, improvement_task: ImprovementTask
) -> RoadmapItemRead:
    assert roadmap_item.id is not None
    return RoadmapItemRead(
        id=roadmap_item.id,
        improvement_task_id=roadmap_item.improvement_task_id,
        title=improvement_task.title,
        description=improvement_task.description,
        status=roadmap_item.status.value,
        priority=roadmap_item.priority,
        estimated_effort=roadmap_item.estimated_effort,
        estimated_impact=roadmap_item.estimated_impact,
        promoted_at=roadmap_item.promoted_at,
        done_at=roadmap_item.done_at,
    )
```

```python
@router.get("/repositories/{repository_id}/roadmap", response_model=list[RoadmapItemRead])
def list_roadmap_items(
    repository_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
) -> list[RoadmapItemRead]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    rows = session.exec(
        select(RoadmapItem, ImprovementTask)
        .join(ImprovementTask, ImprovementTask.id == RoadmapItem.improvement_task_id)  # type: ignore[arg-type]
        .join(
            FindingImprovementTaskLink,
            FindingImprovementTaskLink.improvement_task_id == ImprovementTask.id,  # type: ignore[arg-type]
        )
        .join(Finding, Finding.id == FindingImprovementTaskLink.finding_id)  # type: ignore[arg-type]
        .join(ScoringRun, ScoringRun.id == Finding.scoring_run_id)  # type: ignore[arg-type]
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .distinct()
    ).all()
    return [_to_roadmap_item_read(item, task) for item, task in rows]
```

`update_roadmap_item_status` builds its return value from a single `roadmap_item` it already
fetched with `session.get`; it now needs the linked `ImprovementTask` too. Modify its final lines:

```python
    roadmap_item.status = payload.status
    session.add(roadmap_item)
    session.commit()
    session.refresh(roadmap_item)
    improvement_task = session.get(ImprovementTask, roadmap_item.improvement_task_id)
    assert improvement_task is not None
    return _to_roadmap_item_read(roadmap_item, improvement_task)
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v`
Expected: PASS (16 tests total)

- [ ] **Step 6: Run the full `radar-api` suite and static checks**

Run: `cd radar-api && uv run pytest -v && uv run ruff check . && uv run mypy src`
Expected: PASS, no errors

- [ ] **Step 7: Commit**

```bash
git add radar-api/src/radar_api/schemas/roadmap.py radar-api/src/radar_api/routers/roadmap.py radar-api/tests/test_roadmap.py
git commit -m "feat(radar-api): add title/description to RoadmapItemRead"
```

---

### Task 3: Frontend project scaffolding

**Files:**
- Create: `radar-dashboard/package.json`
- Create: `radar-dashboard/vite.config.ts`
- Create: `radar-dashboard/vitest.config.ts`
- Create: `radar-dashboard/tsconfig.json`
- Create: `radar-dashboard/tsconfig.app.json`
- Create: `radar-dashboard/tsconfig.node.json`
- Create: `radar-dashboard/tsconfig.vitest.json`
- Create: `radar-dashboard/eslint.config.js`
- Create: `radar-dashboard/.oxlintrc.json`
- Create: `radar-dashboard/.prettierrc`
- Create: `radar-dashboard/.gitignore`
- Create: `radar-dashboard/env.d.ts`
- Create: `radar-dashboard/index.html`
- Create: `radar-dashboard/src/main.ts`
- Create: `radar-dashboard/src/App.vue`
- Test: `radar-dashboard/src/__tests__/App.spec.ts`

**Interfaces:**
- Produces: a working Vite + Vitest + TypeScript + ESLint toolchain that every later task builds
  on; `App.vue` is replaced (not created fresh) in Task 14 once real views and the router exist

**Design note:** this mirrors `Triton/frontend`'s toolchain exactly (same dependency versions,
same config shape), minus `vitest-canvas-mock`/`vite-plugin-vue-devtools`'s `HMR_PORT` override
(Triton-specific, not needed here) and plus `vue-router` (Triton has no router; this SPA needs
one). This task's only functional code is a smoke-test placeholder — real screens start at Task 4.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "radar-dashboard",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "run-p type-check \"build-only {@}\" --",
    "preview": "vite preview",
    "test:unit": "vitest",
    "build-only": "vite build",
    "type-check": "vue-tsc --build",
    "lint": "run-s \"lint:*\"",
    "lint:oxlint": "oxlint . --fix",
    "lint:eslint": "eslint . --fix --cache",
    "format": "prettier --write --experimental-cli src/"
  },
  "dependencies": {
    "pinia": "^3.0.4",
    "vue": "^3.5.38",
    "vue-router": "^5.3.1"
  },
  "devDependencies": {
    "@tsconfig/node24": "^24.0.4",
    "@types/jsdom": "^28.0.3",
    "@types/node": "^24.13.2",
    "@vitejs/plugin-vue": "^6.0.7",
    "@vitest/eslint-plugin": "^1.6.20",
    "@vue/eslint-config-typescript": "^14.8.0",
    "@vue/test-utils": "^2.4.11",
    "@vue/tsconfig": "^0.9.1",
    "eslint": "^10.5.0",
    "eslint-config-prettier": "^10.1.8",
    "eslint-plugin-oxlint": "~1.69.0",
    "eslint-plugin-vue": "~10.9.2",
    "jiti": "^2.7.0",
    "jsdom": "^29.1.1",
    "npm-run-all2": "^9.0.2",
    "oxlint": "~1.69.0",
    "prettier": "3.8.4",
    "typescript": "~6.0.0",
    "vite": "^8.0.16",
    "vite-plugin-vue-devtools": "^8.1.2",
    "vitest": "^4.1.9",
    "vue-eslint-parser": "^10.4.1",
    "vue-tsc": "^3.3.5"
  },
  "engines": {
    "node": "^22.18.0 || ^23.0.0 || >=24.12.0"
  }
}
```

- [ ] **Step 2: Create `vite.config.ts`**

```typescript
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

- [ ] **Step 3: Create `vitest.config.ts`**

```typescript
import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
    },
  }),
)
```

- [ ] **Step 4: Create the TypeScript config files**

`radar-dashboard/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.node.json" },
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.vitest.json" }
  ]
}
```

`radar-dashboard/tsconfig.app.json`:

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "include": ["env.d.ts", "src/**/*", "src/**/*.vue"],
  "exclude": ["src/**/__tests__/*"],
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "paths": {
      "@/*": ["./src/*"]
    },
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo"
  }
}
```

`radar-dashboard/tsconfig.node.json`:

```json
{
  "extends": "@tsconfig/node24/tsconfig.json",
  "include": ["vite.config.*", "vitest.config.*", "eslint.config.*"],
  "compilerOptions": {
    "module": "preserve",
    "moduleResolution": "bundler",
    "types": ["node"],
    "noEmit": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo"
  }
}
```

`radar-dashboard/tsconfig.vitest.json`:

```json
{
  "extends": "./tsconfig.app.json",
  "include": ["src/**/__tests__/*", "env.d.ts"],
  "exclude": [],
  "compilerOptions": {
    "lib": [],
    "types": ["node", "jsdom"],
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.vitest.tsbuildinfo"
  }
}
```

- [ ] **Step 5: Create the lint/format config files**

`radar-dashboard/eslint.config.js`:

```javascript
import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import pluginVitest from '@vitest/eslint-plugin'
import pluginOxlint from 'eslint-plugin-oxlint'
import skipFormatting from 'eslint-config-prettier/flat'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{vue,ts,mts,tsx}'],
  },

  globalIgnores(['**/dist/**', '**/dist-ssr/**', '**/coverage/**']),

  ...pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*'],
  },

  ...pluginOxlint.buildFromOxlintConfigFile('.oxlintrc.json'),

  skipFormatting,
)
```

`radar-dashboard/.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["eslint", "typescript", "unicorn", "oxc", "vue", "vitest"],
  "env": {
    "browser": true
  },
  "categories": {
    "correctness": "error"
  }
}
```

`radar-dashboard/.prettierrc`:

```json
{
  "$schema": "https://json.schemastore.org/prettierrc",
  "semi": false,
  "singleQuote": true,
  "printWidth": 100
}
```

`radar-dashboard/.gitignore`:

```
node_modules
.DS_Store
dist
dist-ssr
coverage
*.local

.vscode/*
!.vscode/extensions.json
.idea
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?

*.tsbuildinfo
.eslintcache

*.timestamp-*-*.mjs
```

- [ ] **Step 6: Create `env.d.ts` and `index.html`**

`radar-dashboard/env.d.ts`:

```typescript
/// <reference types="vite/client" />
```

`radar-dashboard/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>radar-dashboard</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 7: Write the failing smoke test**

```typescript
// radar-dashboard/src/__tests__/App.spec.ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import App from '../App.vue'

describe('App', () => {
  it('renders the placeholder heading', () => {
    const wrapper = mount(App)

    expect(wrapper.text()).toContain('radar-dashboard')
  })
})
```

- [ ] **Step 8: Run it, confirm it fails**

Run: `cd radar-dashboard && npm install && npm run test:unit -- --run`
Expected: FAIL (`App.vue` does not exist yet)

- [ ] **Step 9: Create `main.ts` and the placeholder `App.vue`**

```typescript
// radar-dashboard/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

const app = createApp(App)

app.use(createPinia())

app.mount('#app')
```

```vue
<!-- radar-dashboard/src/App.vue -->
<template>
  <main>
    <h1>radar-dashboard</h1>
  </main>
</template>

<script setup lang="ts"></script>
```

- [ ] **Step 10: Run it, confirm it passes**

Run: `cd radar-dashboard && npm run test:unit -- --run`
Expected: PASS (1 test)

- [ ] **Step 11: Confirm type-checking and linting run clean**

Run: `cd radar-dashboard && npm run type-check && npm run lint`
Expected: PASS, no errors

- [ ] **Step 12: Commit**

```bash
git add radar-dashboard/
git commit -m "chore(radar-dashboard): scaffold Vue 3 + Vite + Vitest project"
```

---

### Task 4: `stores/apiKey.ts` — session-scoped API key

**Files:**
- Create: `radar-dashboard/src/stores/apiKey.ts`
- Test: `radar-dashboard/src/stores/__tests__/apiKey.spec.ts`

**Interfaces:**
- Produces: `useApiKeyStore()` returning `{ apiKey: Ref<string>, setApiKey(value: string): void }`
  (consumed by `api/client.ts` in Task 5 and `SettingsView.vue` in Task 13)

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/stores/__tests__/apiKey.spec.ts
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useApiKeyStore } from '../apiKey'

const STORAGE_KEY = 'radar-dashboard/api-key'

describe('apiKey store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
  })

  it('starts empty when nothing is stored', () => {
    const store = useApiKeyStore()

    expect(store.apiKey).toBe('')
  })

  it('reads a previously stored key on creation', () => {
    sessionStorage.setItem(STORAGE_KEY, 'previous-key')

    const store = useApiKeyStore()

    expect(store.apiKey).toBe('previous-key')
  })

  it('setApiKey updates the store and sessionStorage', () => {
    const store = useApiKeyStore()

    store.setApiKey('new-key')

    expect(store.apiKey).toBe('new-key')
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('new-key')
  })

  it('setApiKey with an empty string clears sessionStorage', () => {
    const store = useApiKeyStore()
    store.setApiKey('new-key')

    store.setApiKey('')

    expect(store.apiKey).toBe('')
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run apiKey`
Expected: FAIL (`../apiKey` does not exist)

- [ ] **Step 3: Implement the store**

```typescript
// radar-dashboard/src/stores/apiKey.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'radar-dashboard/api-key'

export const useApiKeyStore = defineStore('apiKey', () => {
  const apiKey = ref<string>(sessionStorage.getItem(STORAGE_KEY) ?? '')

  function setApiKey(value: string): void {
    apiKey.value = value
    if (value) {
      sessionStorage.setItem(STORAGE_KEY, value)
    } else {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }

  return { apiKey, setApiKey }
})
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run apiKey`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/stores/apiKey.ts radar-dashboard/src/stores/__tests__/apiKey.spec.ts
git commit -m "feat(radar-dashboard): add session-scoped API key store"
```

---

### Task 5: `api/client.ts` — typed fetch wrapper for every `radar-api` endpoint

**Files:**
- Create: `radar-dashboard/src/api/client.ts`
- Test: `radar-dashboard/src/api/__tests__/client.spec.ts`

**Interfaces:**
- Consumes: `useApiKeyStore` (Task 4)
- Produces: `ApiError` (class, has `status: number`), TypeScript interfaces `RepositoryRead`,
  `FindingReport`, `CriterionReport`, `CategoryReport`, `RepositoryReport`, `RoadmapItemRead`,
  `EvidenceCandidate` (all consumed by stores/components from Task 6 onward), functions
  `listRepositories()`, `getRepositoryReport(id)`, `getRepositoryRoadmap(id)`,
  `getRoadmapItemEvidenceCandidates(id)`, `updateFindingVerdict(id, humanVerdict)`,
  `updateFindingStatus(id, status)`, `updateRoadmapItemStatus(id, status, doneEvidenceId?)`

**Design note:** interfaces mirror `radar-api`'s Pydantic response schemas field-for-field —
`RepositoryRead` matches `radar_api.schemas.repositories.RepositoryRead`, `RepositoryReport`/
`CategoryReport`/`CriterionReport`/`FindingReport` match `radar_api.schemas.report.*`,
`RoadmapItemRead` matches the Task 2 extended schema, `EvidenceCandidate` matches the Task 1
schema.

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/api/__tests__/client.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useApiKeyStore } from '@/stores/apiKey'
import {
  ApiError,
  getRepositoryReport,
  getRoadmapItemEvidenceCandidates,
  listRepositories,
  updateFindingStatus,
  updateFindingVerdict,
  updateRoadmapItemStatus,
} from '../client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api/client', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn())
  })

  it('listRepositories calls GET /api/repositories and returns the parsed body', async () => {
    const repos = [
      { id: 1, name: 'repo', path: '/tmp/repo', global_score: null, audit_status: 'not_yet_audited' },
    ]
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(repos))

    const result = await listRepositories()

    expect(fetch).toHaveBeenCalledWith('/api/repositories', {})
    expect(result).toEqual(repos)
  })

  it('getRepositoryReport calls GET /api/repositories/:id/report', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ repository_id: 1, categories: [] }))

    await getRepositoryReport(1)

    expect(fetch).toHaveBeenCalledWith('/api/repositories/1/report', {})
  })

  it('getRoadmapItemEvidenceCandidates calls GET /api/roadmap-items/:id/evidence-candidates', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse([]))

    await getRoadmapItemEvidenceCandidates(7)

    expect(fetch).toHaveBeenCalledWith('/api/roadmap-items/7/evidence-candidates', {})
  })

  it('throws an ApiError carrying the status and server detail on a non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: 'not found' }, 404))

    await expect(getRepositoryReport(999)).rejects.toMatchObject({
      status: 404,
      message: 'not found',
    })
  })

  it('falls back to statusText when the error body is not JSON', async () => {
    const response = new Response('plain text', { status: 500, statusText: 'Server Error' })
    vi.mocked(fetch).mockResolvedValueOnce(response)

    await expect(getRepositoryReport(1)).rejects.toMatchObject({
      status: 500,
      message: 'Server Error',
    })
  })

  it('sends the X-API-Key header from the apiKey store on a write call', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateFindingStatus(1, 'RESOLVED')

    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('/api/findings/1/status')
    expect((init?.headers as Record<string, string>)['X-API-Key']).toBe('secret')
    expect(JSON.parse(init?.body as string)).toEqual({ status: 'RESOLVED' })
  })

  it('sends human_verdict as the body for updateFindingVerdict', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateFindingVerdict(1, 'TRUE_POSITIVE')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    expect(JSON.parse(init?.body as string)).toEqual({ human_verdict: 'TRUE_POSITIVE' })
  })

  it('omits done_evidence_id entirely for a non-DONE roadmap status update', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateRoadmapItemStatus(1, 'IN_PROGRESS')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const body = JSON.parse(init?.body as string) as Record<string, unknown>
    expect('done_evidence_id' in body).toBe(false)
  })

  it('includes done_evidence_id for a DONE roadmap status update', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateRoadmapItemStatus(1, 'DONE', 42)

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const body = JSON.parse(init?.body as string) as Record<string, unknown>
    expect(body.done_evidence_id).toBe(42)
  })

  it('ApiError is an instance of Error', () => {
    const error = new ApiError(401, 'invalid or missing API key')

    expect(error).toBeInstanceOf(Error)
    expect(error.status).toBe(401)
    expect(error.message).toBe('invalid or missing API key')
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run client`
Expected: FAIL (`../client` does not exist)

- [ ] **Step 3: Implement `client.ts`**

```typescript
// radar-dashboard/src/api/client.ts
import { useApiKeyStore } from '@/stores/apiKey'

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface RepositoryRead {
  id: number
  name: string
  path: string
  global_score: number | null
  audit_status: 'scored' | 'not_yet_audited'
}

export interface FindingReport {
  id: number
  severity: string
  description: string
  file: string | null
  line: number | null
  status: string
  human_verdict: string
  recommendation: string | null
}

export interface CriterionReport {
  id: number
  name: string
  status: 'scored' | 'not_applicable' | 'not_yet_audited'
  value: number | null
  na_reason: string | null
  findings: FindingReport[]
}

export interface CategoryReport {
  id: number
  name: string
  order: number
  status: 'scored' | 'not_yet_audited'
  value: number | null
  confidence: string | null
  criteria: CriterionReport[]
}

export interface RepositoryReport {
  repository_id: number
  repository_name: string
  commit_sha: string
  audited_at: string
  scored_at: string
  categories: CategoryReport[]
}

export interface RoadmapItemRead {
  id: number
  improvement_task_id: number
  title: string
  description: string
  status: string
  priority: number
  estimated_effort: string | null
  estimated_impact: string | null
  promoted_at: string
  done_at: string | null
}

export interface EvidenceCandidate {
  id: number
  finding_id: number
  evidence_type: string
  content: string
  created_at: string
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, init)

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // response body was not JSON; keep statusText
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function writeHeaders(): HeadersInit {
  const apiKeyStore = useApiKeyStore()
  return {
    'Content-Type': 'application/json',
    'X-API-Key': apiKeyStore.apiKey,
  }
}

export function listRepositories(): Promise<RepositoryRead[]> {
  return request<RepositoryRead[]>('/repositories')
}

export function getRepositoryReport(repositoryId: number): Promise<RepositoryReport> {
  return request<RepositoryReport>(`/repositories/${repositoryId}/report`)
}

export function getRepositoryRoadmap(repositoryId: number): Promise<RoadmapItemRead[]> {
  return request<RoadmapItemRead[]>(`/repositories/${repositoryId}/roadmap`)
}

export function getRoadmapItemEvidenceCandidates(
  roadmapItemId: number,
): Promise<EvidenceCandidate[]> {
  return request<EvidenceCandidate[]>(`/roadmap-items/${roadmapItemId}/evidence-candidates`)
}

export function updateFindingVerdict(findingId: number, humanVerdict: string): Promise<void> {
  return request<void>(`/findings/${findingId}/verdict`, {
    method: 'PATCH',
    headers: writeHeaders(),
    body: JSON.stringify({ human_verdict: humanVerdict }),
  })
}

export function updateFindingStatus(findingId: number, status: string): Promise<void> {
  return request<void>(`/findings/${findingId}/status`, {
    method: 'PATCH',
    headers: writeHeaders(),
    body: JSON.stringify({ status }),
  })
}

export function updateRoadmapItemStatus(
  roadmapItemId: number,
  status: string,
  doneEvidenceId?: number,
): Promise<void> {
  const body: Record<string, unknown> = { status }
  if (doneEvidenceId !== undefined) {
    body.done_evidence_id = doneEvidenceId
  }
  return request<void>(`/roadmap-items/${roadmapItemId}/status`, {
    method: 'PATCH',
    headers: writeHeaders(),
    body: JSON.stringify(body),
  })
}
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run client`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/api/client.ts radar-dashboard/src/api/__tests__/client.spec.ts
git commit -m "feat(radar-dashboard): add typed radar-api client"
```

---

### Task 6: `stores/repositories.ts` — fetched data and loading/error state

**Files:**
- Create: `radar-dashboard/src/stores/repositories.ts`
- Test: `radar-dashboard/src/stores/__tests__/repositories.spec.ts`

**Interfaces:**
- Consumes: `listRepositories`, `getRepositoryReport`, `getRepositoryRoadmap` (Task 5)
- Produces: `useRepositoriesStore()` returning `list`, `listLoading`, `listError`, `fetchList()`,
  `report`, `reportLoading`, `reportError`, `fetchReport(id)`, `roadmap`, `roadmapLoading`,
  `roadmapError`, `fetchRoadmap(id)` (all consumed by views in Tasks 11-12)

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/stores/__tests__/repositories.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as client from '@/api/client'
import { useRepositoriesStore } from '../repositories'

vi.mock('@/api/client')

describe('repositories store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchList populates list on success', async () => {
    const repos = [
      { id: 1, name: 'repo', path: '/tmp/repo', global_score: 7, audit_status: 'scored' as const },
    ]
    vi.mocked(client.listRepositories).mockResolvedValueOnce(repos)
    const store = useRepositoriesStore()

    await store.fetchList()

    expect(store.list).toEqual(repos)
    expect(store.listLoading).toBe(false)
    expect(store.listError).toBeNull()
  })

  it('fetchList sets listError and clears loading on failure', async () => {
    vi.mocked(client.listRepositories).mockRejectedValueOnce(new Error('network down'))
    const store = useRepositoriesStore()

    await store.fetchList()

    expect(store.listError).toBe('network down')
    expect(store.listLoading).toBe(false)
    expect(store.list).toEqual([])
  })

  it('fetchReport populates report on success', async () => {
    const report = { repository_id: 1, repository_name: 'repo', commit_sha: 'a', audited_at: '2026-01-01', scored_at: '2026-01-01', categories: [] }
    vi.mocked(client.getRepositoryReport).mockResolvedValueOnce(report)
    const store = useRepositoriesStore()

    await store.fetchReport(1)

    expect(store.report).toEqual(report)
    expect(store.reportError).toBeNull()
  })

  it('fetchReport sets reportError on failure', async () => {
    vi.mocked(client.getRepositoryReport).mockRejectedValueOnce(new Error('not found'))
    const store = useRepositoriesStore()

    await store.fetchReport(999)

    expect(store.reportError).toBe('not found')
    expect(store.report).toBeNull()
  })

  it('fetchRoadmap populates roadmap on success', async () => {
    const items = [
      {
        id: 1,
        improvement_task_id: 1,
        title: 'Fix it',
        description: '...',
        status: 'TODO',
        priority: 1,
        estimated_effort: null,
        estimated_impact: null,
        promoted_at: '2026-01-01',
        done_at: null,
      },
    ]
    vi.mocked(client.getRepositoryRoadmap).mockResolvedValueOnce(items)
    const store = useRepositoriesStore()

    await store.fetchRoadmap(1)

    expect(store.roadmap).toEqual(items)
    expect(store.roadmapError).toBeNull()
  })

  it('fetchRoadmap sets roadmapError on failure', async () => {
    vi.mocked(client.getRepositoryRoadmap).mockRejectedValueOnce(new Error('boom'))
    const store = useRepositoriesStore()

    await store.fetchRoadmap(1)

    expect(store.roadmapError).toBe('boom')
    expect(store.roadmap).toEqual([])
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run repositories`
Expected: FAIL (`../repositories` does not exist)

- [ ] **Step 3: Implement the store**

```typescript
// radar-dashboard/src/stores/repositories.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as client from '@/api/client'
import type { RepositoryRead, RepositoryReport, RoadmapItemRead } from '@/api/client'

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'unexpected error'
}

export const useRepositoriesStore = defineStore('repositories', () => {
  const list = ref<RepositoryRead[]>([])
  const listLoading = ref(false)
  const listError = ref<string | null>(null)

  const report = ref<RepositoryReport | null>(null)
  const reportLoading = ref(false)
  const reportError = ref<string | null>(null)

  const roadmap = ref<RoadmapItemRead[]>([])
  const roadmapLoading = ref(false)
  const roadmapError = ref<string | null>(null)

  async function fetchList(): Promise<void> {
    listLoading.value = true
    listError.value = null
    try {
      list.value = await client.listRepositories()
    } catch (error) {
      listError.value = errorMessage(error)
    } finally {
      listLoading.value = false
    }
  }

  async function fetchReport(repositoryId: number): Promise<void> {
    reportLoading.value = true
    reportError.value = null
    try {
      report.value = await client.getRepositoryReport(repositoryId)
    } catch (error) {
      reportError.value = errorMessage(error)
    } finally {
      reportLoading.value = false
    }
  }

  async function fetchRoadmap(repositoryId: number): Promise<void> {
    roadmapLoading.value = true
    roadmapError.value = null
    try {
      roadmap.value = await client.getRepositoryRoadmap(repositoryId)
    } catch (error) {
      roadmapError.value = errorMessage(error)
    } finally {
      roadmapLoading.value = false
    }
  }

  return {
    list,
    listLoading,
    listError,
    fetchList,
    report,
    reportLoading,
    reportError,
    fetchReport,
    roadmap,
    roadmapLoading,
    roadmapError,
    fetchRoadmap,
  }
})
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run repositories`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/stores/repositories.ts radar-dashboard/src/stores/__tests__/repositories.spec.ts
git commit -m "feat(radar-dashboard): add repositories store with loading/error state"
```

---

### Task 7: `ScoreGauge.vue` — flat-band score gauge

**Files:**
- Create: `radar-dashboard/src/components/ScoreGauge.vue`
- Test: `radar-dashboard/src/components/__tests__/ScoreGauge.spec.ts`

**Interfaces:**
- Produces: `ScoreGauge.vue` with props `value: number | null`,
  `status: 'scored' | 'not_applicable' | 'not_yet_audited'`, `naReason?: string | null` (consumed
  by Tasks 11-12's views)

**Covers Review Focus #1** (a `not_applicable`/`not_yet_audited` gauge must never try to compute a
color band from a `null` value).

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/components/__tests__/ScoreGauge.spec.ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ScoreGauge from '../ScoreGauge.vue'

describe('ScoreGauge', () => {
  it.each([
    [9, 'score-gauge--brightgreen'],
    [8, 'score-gauge--brightgreen'],
    [7, 'score-gauge--green'],
    [6, 'score-gauge--green'],
    [5, 'score-gauge--yellow'],
    [4, 'score-gauge--yellow'],
    [3, 'score-gauge--orange'],
    [2, 'score-gauge--orange'],
    [1, 'score-gauge--red'],
    [0, 'score-gauge--red'],
  ])('renders band %s -> %s for a scored value', (value, expectedClass) => {
    const wrapper = mount(ScoreGauge, { props: { value, status: 'scored' } })

    expect(wrapper.classes()).toContain(expectedClass)
  })

  it('renders the not_applicable gray with the reason, and does not crash on a null value', () => {
    const wrapper = mount(ScoreGauge, {
      props: { value: null, status: 'not_applicable', naReason: 'no test suite exists' },
    })

    expect(wrapper.classes()).toContain('score-gauge--na')
    expect(wrapper.attributes('title')).toBe('no test suite exists')
  })

  it('renders the not_yet_audited gray, distinct from not_applicable', () => {
    const wrapper = mount(ScoreGauge, { props: { value: null, status: 'not_yet_audited' } })

    expect(wrapper.classes()).toContain('score-gauge--pending')
    expect(wrapper.classes()).not.toContain('score-gauge--na')
    expect(wrapper.attributes('title')).toBe('not yet audited')
  })

  it('toggles the reason popover on click for a non-scored gauge', async () => {
    const wrapper = mount(ScoreGauge, {
      props: { value: null, status: 'not_applicable', naReason: 'no test suite exists' },
    })

    expect(wrapper.find('.score-gauge__reason').exists()).toBe(false)

    await wrapper.trigger('click')

    expect(wrapper.find('.score-gauge__reason').text()).toBe('no test suite exists')
  })

  it('does not toggle a popover on click for a scored gauge', async () => {
    const wrapper = mount(ScoreGauge, { props: { value: 9, status: 'scored' } })

    await wrapper.trigger('click')

    expect(wrapper.find('.score-gauge__reason').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run ScoreGauge`
Expected: FAIL (`../ScoreGauge.vue` does not exist)

- [ ] **Step 3: Implement the component**

```vue
<!-- radar-dashboard/src/components/ScoreGauge.vue -->
<template>
  <span
    class="score-gauge"
    :class="bandClass"
    :title="reasonText ?? undefined"
    tabindex="0"
    @click="toggleReason"
  >
    <span class="score-gauge__value">{{ displayValue }}</span>
    <span v-if="reasonVisible && reasonText" class="score-gauge__reason" role="tooltip">
      {{ reasonText }}
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  value: number | null
  status: 'scored' | 'not_applicable' | 'not_yet_audited'
  naReason?: string | null
}>()

const reasonVisible = ref(false)

function toggleReason(): void {
  if (props.status !== 'scored') {
    reasonVisible.value = !reasonVisible.value
  }
}

const bandClass = computed(() => {
  if (props.status === 'not_applicable') return 'score-gauge--na'
  if (props.status === 'not_yet_audited') return 'score-gauge--pending'

  const value = props.value ?? 0
  if (value >= 8) return 'score-gauge--brightgreen'
  if (value >= 6) return 'score-gauge--green'
  if (value >= 4) return 'score-gauge--yellow'
  if (value >= 2) return 'score-gauge--orange'
  return 'score-gauge--red'
})

const displayValue = computed(() => {
  if (props.status === 'scored' && props.value !== null) {
    return props.value.toFixed(1)
  }
  return props.status === 'not_applicable' ? 'N/A' : '—'
})

const reasonText = computed(() => {
  if (props.status === 'not_applicable') return props.naReason ?? 'not applicable'
  if (props.status === 'not_yet_audited') return 'not yet audited'
  return null
})
</script>

<style scoped>
.score-gauge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 3rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-weight: 600;
  color: #1a1a1a;
  position: relative;
}
.score-gauge--brightgreen {
  background-color: #2ecc71;
}
.score-gauge--green {
  background-color: #6fcf97;
}
.score-gauge--yellow {
  background-color: #f2c94c;
}
.score-gauge--orange {
  background-color: #f2994a;
}
.score-gauge--red {
  background-color: #eb5757;
  color: #f5f5f5;
}
.score-gauge--na {
  background-color: #9a9a9a;
  color: #f5f5f5;
  cursor: pointer;
}
.score-gauge--pending {
  background-color: #d4d4d4;
  color: #4a4a4a;
  cursor: pointer;
}
.score-gauge__reason {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: #1a1a1a;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 400;
  border-radius: 0.25rem;
  white-space: nowrap;
  z-index: 10;
}
</style>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run ScoreGauge`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/components/ScoreGauge.vue radar-dashboard/src/components/__tests__/ScoreGauge.spec.ts
git commit -m "feat(radar-dashboard): add ScoreGauge flat-band component"
```

---

### Task 8: `FindingCard.vue` — severity badge, recommendation, verdict/status controls

**Files:**
- Create: `radar-dashboard/src/components/FindingCard.vue`
- Test: `radar-dashboard/src/components/__tests__/FindingCard.spec.ts`

**Interfaces:**
- Consumes: `updateFindingVerdict`, `updateFindingStatus`, `ApiError` (Task 5)
- Produces: `FindingCard.vue` with prop `finding: FindingReport`, emits `updated` (consumed by
  `RepositoryDetailView.vue`, Task 12)

**Covers Review Focus #4** (a `401` on a write must surface an inline message, not fail silently).

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/components/__tests__/FindingCard.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import * as client from '@/api/client'
import { ApiError } from '@/api/client'
import FindingCard from '../FindingCard.vue'
import type { FindingReport } from '@/api/client'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, updateFindingVerdict: vi.fn(), updateFindingStatus: vi.fn() }
})

const finding: FindingReport = {
  id: 1,
  severity: 'HIGH',
  description: 'a vulnerable dependency',
  file: null,
  line: null,
  status: 'OPEN',
  human_verdict: 'UNREVIEWED',
  recommendation: 'upgrade the dependency',
}

describe('FindingCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the severity badge and the recommendation text', () => {
    const wrapper = mount(FindingCard, { props: { finding } })

    expect(wrapper.classes()).toContain('finding-card--high')
    expect(wrapper.text()).toContain('upgrade the dependency')
  })

  it('submits a verdict change and emits updated', async () => {
    vi.mocked(client.updateFindingVerdict).mockResolvedValueOnce(undefined)
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="verdict-select"]').setValue('TRUE_POSITIVE')

    expect(client.updateFindingVerdict).toHaveBeenCalledWith(1, 'TRUE_POSITIVE')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('submits a status change and emits updated', async () => {
    vi.mocked(client.updateFindingStatus).mockResolvedValueOnce(undefined)
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="status-select"]').setValue('RESOLVED')

    expect(client.updateFindingStatus).toHaveBeenCalledWith(1, 'RESOLVED')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('shows an inline message directing to Settings on a 401', async () => {
    vi.mocked(client.updateFindingStatus).mockRejectedValueOnce(
      new ApiError(401, 'invalid or missing API key'),
    )
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="status-select"]').setValue('RESOLVED')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Settings')
    expect(wrapper.emitted('updated')).toBeUndefined()
  })

  it('shows the raw error message for a non-401 failure', async () => {
    vi.mocked(client.updateFindingStatus).mockRejectedValueOnce(new Error('server exploded'))
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="status-select"]').setValue('RESOLVED')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('server exploded')
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run FindingCard`
Expected: FAIL (`../FindingCard.vue` does not exist)

- [ ] **Step 3: Implement the component**

```vue
<!-- radar-dashboard/src/components/FindingCard.vue -->
<template>
  <div class="finding-card" :class="severityClass">
    <div class="finding-card__header">
      <span class="finding-card__severity">{{ finding.severity }}</span>
      <span class="finding-card__description">{{ finding.description }}</span>
    </div>
    <p v-if="finding.recommendation" class="finding-card__recommendation">
      {{ finding.recommendation }}
    </p>
    <div class="finding-card__controls">
      <label>
        Verdict
        <select data-testid="verdict-select" v-model="verdict" @change="submitVerdict">
          <option value="UNREVIEWED">Unreviewed</option>
          <option value="TRUE_POSITIVE">True positive</option>
          <option value="FALSE_POSITIVE">False positive</option>
        </select>
      </label>
      <label>
        Status
        <select data-testid="status-select" v-model="status" @change="submitStatus">
          <option value="OPEN">Open</option>
          <option value="RESOLVED">Resolved</option>
          <option value="WONT_FIX">Won't fix</option>
        </select>
      </label>
    </div>
    <p v-if="errorMessage" class="finding-card__error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FindingReport } from '@/api/client'
import { ApiError, updateFindingStatus, updateFindingVerdict } from '@/api/client'

const props = defineProps<{ finding: FindingReport }>()
const emit = defineEmits<{ updated: [] }>()

const verdict = ref(props.finding.human_verdict)
const status = ref(props.finding.status)
const errorMessage = ref<string | null>(null)

const severityClass = computed(() => `finding-card--${props.finding.severity.toLowerCase()}`)

function handleError(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    errorMessage.value = 'Missing or invalid API key — set it in Settings.'
  } else {
    errorMessage.value = error instanceof Error ? error.message : 'update failed'
  }
}

async function submitVerdict(): Promise<void> {
  errorMessage.value = null
  try {
    await updateFindingVerdict(props.finding.id, verdict.value)
    emit('updated')
  } catch (error) {
    handleError(error)
  }
}

async function submitStatus(): Promise<void> {
  errorMessage.value = null
  try {
    await updateFindingStatus(props.finding.id, status.value)
    emit('updated')
  } catch (error) {
    handleError(error)
  }
}
</script>

<style scoped>
.finding-card {
  border-left: 4px solid transparent;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
}
.finding-card--critical {
  border-left-color: #eb5757;
}
.finding-card--high {
  border-left-color: #f2994a;
}
.finding-card--medium {
  border-left-color: #f2c94c;
}
.finding-card--low {
  border-left-color: #6fcf97;
}
.finding-card--info {
  border-left-color: #56ccf2;
}
.finding-card__error {
  color: #eb5757;
  font-size: 0.875rem;
}
</style>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run FindingCard`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/components/FindingCard.vue radar-dashboard/src/components/__tests__/FindingCard.spec.ts
git commit -m "feat(radar-dashboard): add FindingCard with verdict/status controls"
```

---

### Task 9: `EvidencePicker.vue` — evidence-candidates picker

**Files:**
- Create: `radar-dashboard/src/components/EvidencePicker.vue`
- Test: `radar-dashboard/src/components/__tests__/EvidencePicker.spec.ts`

**Interfaces:**
- Consumes: `getRoadmapItemEvidenceCandidates` (Task 5)
- Produces: `EvidencePicker.vue` with prop `roadmapItemId: number`, emits
  `select: [evidenceId: number]` (consumed by `RoadmapItemRow.vue`, Task 10)

**Covers Review Focus #5** (an empty candidate list must show a message, not an empty picker).

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/components/__tests__/EvidencePicker.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import * as client from '@/api/client'
import EvidencePicker from '../EvidencePicker.vue'

vi.mock('@/api/client')

describe('EvidencePicker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a message instead of a picker when there are no candidates', async () => {
    vi.mocked(client.getRoadmapItemEvidenceCandidates).mockResolvedValueOnce([])

    const wrapper = mount(EvidencePicker, { props: { roadmapItemId: 1 } })
    await flushPromises()

    expect(wrapper.find('.evidence-picker__empty').exists()).toBe(true)
    expect(wrapper.findAll('input[type="radio"]')).toHaveLength(0)
  })

  it('renders one radio per candidate and emits select on choice', async () => {
    vi.mocked(client.getRoadmapItemEvidenceCandidates).mockResolvedValueOnce([
      { id: 5, finding_id: 1, evidence_type: 'HUMAN_CONFIRMATION', content: 'fixed in PR #123', created_at: '2026-01-01' },
      { id: 6, finding_id: 1, evidence_type: 'TOOL_OUTPUT_EXCERPT', content: 'lint output', created_at: '2026-01-02' },
    ])

    const wrapper = mount(EvidencePicker, { props: { roadmapItemId: 1 } })
    await flushPromises()

    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios).toHaveLength(2)

    await radios[0]!.setValue()

    expect(wrapper.emitted('select')).toEqual([[5]])
  })

  it('truncates a long content preview', async () => {
    const longContent = 'x'.repeat(200)
    vi.mocked(client.getRoadmapItemEvidenceCandidates).mockResolvedValueOnce([
      { id: 5, finding_id: 1, evidence_type: 'TOOL_OUTPUT_EXCERPT', content: longContent, created_at: '2026-01-01' },
    ])

    const wrapper = mount(EvidencePicker, { props: { roadmapItemId: 1 } })
    await flushPromises()

    expect(wrapper.text()).not.toContain(longContent)
    expect(wrapper.text()).toContain('x'.repeat(80))
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run EvidencePicker`
Expected: FAIL (`../EvidencePicker.vue` does not exist)

- [ ] **Step 3: Implement the component**

```vue
<!-- radar-dashboard/src/components/EvidencePicker.vue -->
<template>
  <div class="evidence-picker">
    <p v-if="loading">Loading evidence…</p>
    <p v-else-if="error" class="evidence-picker__error">{{ error }}</p>
    <p v-else-if="candidates.length === 0" class="evidence-picker__empty">
      No evidence linked to this roadmap item's findings yet.
    </p>
    <ul v-else class="evidence-picker__list">
      <li v-for="candidate in candidates" :key="candidate.id">
        <label>
          <input
            type="radio"
            name="evidence-candidate"
            :value="candidate.id"
            v-model="selectedId"
            @change="emitSelection"
          />
          <strong>{{ candidate.evidence_type }}</strong>
          — {{ preview(candidate.content) }}
        </label>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { EvidenceCandidate } from '@/api/client'
import { getRoadmapItemEvidenceCandidates } from '@/api/client'

const props = defineProps<{ roadmapItemId: number }>()
const emit = defineEmits<{ select: [evidenceId: number] }>()

const candidates = ref<EvidenceCandidate[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

function preview(content: string): string {
  return content.length > 80 ? `${content.slice(0, 80)}…` : content
}

function emitSelection(): void {
  if (selectedId.value !== null) {
    emit('select', selectedId.value)
  }
}

onMounted(async () => {
  try {
    candidates.value = await getRoadmapItemEvidenceCandidates(props.roadmapItemId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'failed to load evidence'
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run EvidencePicker`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/components/EvidencePicker.vue radar-dashboard/src/components/__tests__/EvidencePicker.spec.ts
git commit -m "feat(radar-dashboard): add EvidencePicker component"
```

---

### Task 10: `RoadmapItemRow.vue` — status transitions and the `DONE` evidence gate

**Files:**
- Create: `radar-dashboard/src/components/RoadmapItemRow.vue`
- Test: `radar-dashboard/src/components/__tests__/RoadmapItemRow.spec.ts`

**Interfaces:**
- Consumes: `EvidencePicker.vue` (Task 9), `updateRoadmapItemStatus`, `ApiError` (Task 5)
- Produces: `RoadmapItemRow.vue` with prop `item: RoadmapItemRead`, emits `updated` (consumed by
  `RepositoryDetailView.vue`, Task 12)

**Covers Review Focus #2** (omit `done_evidence_id` entirely for non-`DONE` transitions) and
**Review Focus #4** (401 message) at the component-wiring level — the payload-shape assertion
itself lives in Task 5's `client.spec.ts`.

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/components/__tests__/RoadmapItemRow.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import * as client from '@/api/client'
import { ApiError } from '@/api/client'
import RoadmapItemRow from '../RoadmapItemRow.vue'
import EvidencePicker from '../EvidencePicker.vue'
import type { RoadmapItemRead } from '@/api/client'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, updateRoadmapItemStatus: vi.fn() }
})

const item: RoadmapItemRead = {
  id: 1,
  improvement_task_id: 1,
  title: 'Fix it',
  description: 'a description',
  status: 'IN_PROGRESS',
  priority: 1,
  estimated_effort: null,
  estimated_impact: null,
  promoted_at: '2026-01-01',
  done_at: null,
}

describe('RoadmapItemRow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not show the evidence picker for the initial status', () => {
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    expect(wrapper.findComponent(EvidencePicker).exists()).toBe(false)
  })

  it('shows the evidence picker only when the target status is DONE', async () => {
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    await wrapper.find('select').setValue('DONE')

    expect(wrapper.findComponent(EvidencePicker).exists()).toBe(true)
  })

  it('disables submit for DONE until evidence is selected, then submits with done_evidence_id', async () => {
    vi.mocked(client.updateRoadmapItemStatus).mockResolvedValueOnce(undefined)
    const wrapper = mount(RoadmapItemRow, { props: { item } })
    await wrapper.find('select').setValue('DONE')

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()

    wrapper.findComponent(EvidencePicker).vm.$emit('select', 42)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()

    await wrapper.find('button').trigger('click')

    expect(client.updateRoadmapItemStatus).toHaveBeenCalledWith(1, 'DONE', 42)
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('submits a non-DONE transition without a done_evidence_id argument', async () => {
    vi.mocked(client.updateRoadmapItemStatus).mockResolvedValueOnce(undefined)
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    await wrapper.find('select').setValue('WONT_FIX')
    await wrapper.find('button').trigger('click')

    expect(client.updateRoadmapItemStatus).toHaveBeenCalledWith(1, 'WONT_FIX')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('shows an inline message directing to Settings on a 401', async () => {
    vi.mocked(client.updateRoadmapItemStatus).mockRejectedValueOnce(
      new ApiError(401, 'invalid or missing API key'),
    )
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    await wrapper.find('select').setValue('WONT_FIX')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Settings')
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run RoadmapItemRow`
Expected: FAIL (`../RoadmapItemRow.vue` does not exist)

- [ ] **Step 3: Implement the component**

```vue
<!-- radar-dashboard/src/components/RoadmapItemRow.vue -->
<template>
  <li class="roadmap-item-row">
    <h3>{{ item.title }}</h3>
    <p>{{ item.description }}</p>
    <p class="roadmap-item-row__status">Status: {{ item.status }}</p>
    <p v-if="item.estimated_effort || item.estimated_impact" class="roadmap-item-row__estimates">
      <span v-if="item.estimated_effort">Effort: {{ item.estimated_effort }}</span>
      <span v-if="item.estimated_impact">Impact: {{ item.estimated_impact }}</span>
    </p>
    <label>
      Change status
      <select v-model="targetStatus">
        <option value="TODO">To do</option>
        <option value="IN_PROGRESS">In progress</option>
        <option value="DONE">Done</option>
        <option value="WONT_FIX">Won't fix</option>
      </select>
    </label>
    <EvidencePicker
      v-if="targetStatus === 'DONE'"
      :roadmap-item-id="item.id"
      @select="onEvidenceSelected"
    />
    <button type="button" :disabled="!canSubmit" @click="submit">Apply</button>
    <p v-if="errorMessage" class="roadmap-item-row__error">{{ errorMessage }}</p>
  </li>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import EvidencePicker from './EvidencePicker.vue'
import type { RoadmapItemRead } from '@/api/client'
import { ApiError, updateRoadmapItemStatus } from '@/api/client'

const props = defineProps<{ item: RoadmapItemRead }>()
const emit = defineEmits<{ updated: [] }>()

const targetStatus = ref(props.item.status)
const selectedEvidenceId = ref<number | null>(null)
const errorMessage = ref<string | null>(null)

const canSubmit = computed(() => {
  if (targetStatus.value === props.item.status) return false
  if (targetStatus.value === 'DONE') return selectedEvidenceId.value !== null
  return true
})

function onEvidenceSelected(evidenceId: number): void {
  selectedEvidenceId.value = evidenceId
}

async function submit(): Promise<void> {
  errorMessage.value = null
  try {
    if (targetStatus.value === 'DONE') {
      await updateRoadmapItemStatus(props.item.id, targetStatus.value, selectedEvidenceId.value!)
    } else {
      await updateRoadmapItemStatus(props.item.id, targetStatus.value)
    }
    emit('updated')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = 'Missing or invalid API key — set it in Settings.'
    } else {
      errorMessage.value = error instanceof Error ? error.message : 'update failed'
    }
  }
}
</script>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run RoadmapItemRow`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/components/RoadmapItemRow.vue radar-dashboard/src/components/__tests__/RoadmapItemRow.spec.ts
git commit -m "feat(radar-dashboard): add RoadmapItemRow with DONE evidence gate"
```

---

### Task 11: `RepositoryListView.vue`

**Files:**
- Create: `radar-dashboard/src/views/RepositoryListView.vue`
- Test: `radar-dashboard/src/views/__tests__/RepositoryListView.spec.ts`

**Interfaces:**
- Consumes: `useRepositoriesStore` (Task 6), `ScoreGauge.vue` (Task 7)
- Produces: `RepositoryListView.vue` (mounted at `/` in Task 14)

**Covers Review Focus #3** (loading/error states must actually reach the view) for the repository
list.

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/views/__tests__/RepositoryListView.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useRepositoriesStore } from '@/stores/repositories'
import RepositoryListView from '../RepositoryListView.vue'

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: RepositoryListView },
      { path: '/repositories/:id', component: { template: '<div />' } },
    ],
  })
  router.push('/')
  await router.isReady()
  return mount(RepositoryListView, { global: { plugins: [router] } })
}

describe('RepositoryListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows a loading state while the list is in flight', async () => {
    const store = useRepositoriesStore()
    store.fetchList = vi.fn().mockReturnValue(new Promise(() => {}))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Loading')
  })

  it('shows the error state when listError is set', async () => {
    const store = useRepositoriesStore()
    store.fetchList = vi.fn(async () => {
      store.listError = 'failed to load repositories'
    })

    const wrapper = await mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('failed to load repositories')
  })

  it('renders each repository with a link and a gauge', async () => {
    const store = useRepositoriesStore()
    store.fetchList = vi.fn(async () => {
      store.list = [
        { id: 1, name: 'repo-a', path: '/tmp/repo-a', global_score: 7.5, audit_status: 'scored' },
      ]
    })

    const wrapper = await mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('repo-a')
    expect(wrapper.findComponent({ name: 'ScoreGauge' }).exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run RepositoryListView`
Expected: FAIL (`../RepositoryListView.vue` does not exist)

- [ ] **Step 3: Implement the view**

```vue
<!-- radar-dashboard/src/views/RepositoryListView.vue -->
<template>
  <div class="repository-list-view">
    <h1>Repositories</h1>
    <p v-if="store.listLoading">Loading…</p>
    <p v-else-if="store.listError" class="repository-list-view__error">{{ store.listError }}</p>
    <ul v-else>
      <li v-for="repo in store.list" :key="repo.id">
        <RouterLink :to="`/repositories/${repo.id}`">{{ repo.name }}</RouterLink>
        <ScoreGauge
          :value="repo.global_score"
          :status="repo.audit_status === 'scored' ? 'scored' : 'not_yet_audited'"
        />
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import ScoreGauge from '@/components/ScoreGauge.vue'
import { useRepositoriesStore } from '@/stores/repositories'

const store = useRepositoriesStore()

onMounted(() => {
  store.fetchList()
})
</script>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run RepositoryListView`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/views/RepositoryListView.vue radar-dashboard/src/views/__tests__/RepositoryListView.spec.ts
git commit -m "feat(radar-dashboard): add RepositoryListView"
```

---

### Task 12: `RepositoryDetailView.vue`

**Files:**
- Create: `radar-dashboard/src/views/RepositoryDetailView.vue`
- Test: `radar-dashboard/src/views/__tests__/RepositoryDetailView.spec.ts`

**Interfaces:**
- Consumes: `useRepositoriesStore` (Task 6), `ScoreGauge.vue` (Task 7), `FindingCard.vue`
  (Task 8), `RoadmapItemRow.vue` (Task 10)
- Produces: `RepositoryDetailView.vue` (mounted at `/repositories/:id` in Task 14)

**Covers Review Focus #3** (loading/error states) for the report and roadmap tabs.

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/views/__tests__/RepositoryDetailView.spec.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useRepositoriesStore } from '@/stores/repositories'
import RepositoryDetailView from '../RepositoryDetailView.vue'

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/repositories/:id', component: RepositoryDetailView }],
  })
  router.push('/repositories/1')
  await router.isReady()
  const wrapper = mount(RepositoryDetailView, { global: { plugins: [router] } })
  await wrapper.vm.$nextTick()
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('RepositoryDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the report error state', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn(async () => {
      store.reportError = 'no score found for this repository'
    })
    store.fetchRoadmap = vi.fn()

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('no score found for this repository')
  })

  it('renders categories, criteria, and findings from the report', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn(async () => {
      store.report = {
        repository_id: 1,
        repository_name: 'repo-a',
        commit_sha: 'a',
        audited_at: '2026-01-01',
        scored_at: '2026-01-01',
        categories: [
          {
            id: 1,
            name: 'Security',
            order: 1,
            status: 'scored',
            value: 5,
            confidence: 'HIGH',
            criteria: [
              {
                id: 1,
                name: 'SAST findings',
                status: 'scored',
                value: 4,
                na_reason: null,
                findings: [
                  {
                    id: 1,
                    severity: 'HIGH',
                    description: 'issue',
                    file: null,
                    line: null,
                    status: 'OPEN',
                    human_verdict: 'UNREVIEWED',
                    recommendation: null,
                  },
                ],
              },
            ],
          },
        ],
      }
    })
    store.fetchRoadmap = vi.fn()

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Security')
    expect(wrapper.text()).toContain('SAST findings')
    expect(wrapper.findComponent({ name: 'FindingCard' }).exists()).toBe(true)
  })

  it('switches to the roadmap tab and renders roadmap items', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn()
    store.fetchRoadmap = vi.fn(async () => {
      store.roadmap = [
        {
          id: 1,
          improvement_task_id: 1,
          title: 'Fix it',
          description: '...',
          status: 'TODO',
          priority: 1,
          estimated_effort: null,
          estimated_impact: null,
          promoted_at: '2026-01-01',
          done_at: null,
        },
      ]
    })

    const wrapper = await mountView()
    await wrapper.findAll('button')[1]!.trigger('click')

    expect(wrapper.findComponent({ name: 'RoadmapItemRow' }).exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run RepositoryDetailView`
Expected: FAIL (`../RepositoryDetailView.vue` does not exist)

- [ ] **Step 3: Implement the view**

```vue
<!-- radar-dashboard/src/views/RepositoryDetailView.vue -->
<template>
  <div class="repository-detail-view">
    <nav class="repository-detail-view__tabs">
      <button type="button" :class="{ active: tab === 'report' }" @click="tab = 'report'">
        Report
      </button>
      <button type="button" :class="{ active: tab === 'roadmap' }" @click="tab = 'roadmap'">
        Roadmap
      </button>
    </nav>

    <section v-if="tab === 'report'">
      <p v-if="store.reportLoading">Loading…</p>
      <p v-else-if="store.reportError" class="repository-detail-view__error">
        {{ store.reportError }}
      </p>
      <template v-else-if="store.report">
        <h1>{{ store.report.repository_name }}</h1>
        <div v-for="category in store.report.categories" :key="category.id" class="category">
          <h2>
            {{ category.name }}
            <ScoreGauge :value="category.value" :status="category.status" />
          </h2>
          <div v-for="criterion in category.criteria" :key="criterion.id" class="criterion">
            <h3>
              {{ criterion.name }}
              <ScoreGauge
                :value="criterion.value"
                :status="criterion.status"
                :na-reason="criterion.na_reason"
              />
            </h3>
            <FindingCard
              v-for="finding in criterion.findings"
              :key="finding.id"
              :finding="finding"
              @updated="refetchReport"
            />
          </div>
        </div>
      </template>
    </section>

    <section v-else>
      <p v-if="store.roadmapLoading">Loading…</p>
      <p v-else-if="store.roadmapError" class="repository-detail-view__error">
        {{ store.roadmapError }}
      </p>
      <ul v-else>
        <RoadmapItemRow
          v-for="item in store.roadmap"
          :key="item.id"
          :item="item"
          @updated="refetchRoadmap"
        />
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import ScoreGauge from '@/components/ScoreGauge.vue'
import FindingCard from '@/components/FindingCard.vue'
import RoadmapItemRow from '@/components/RoadmapItemRow.vue'
import { useRepositoriesStore } from '@/stores/repositories'

const route = useRoute()
const store = useRepositoriesStore()
const tab = ref<'report' | 'roadmap'>('report')

const repositoryId = Number(route.params.id)

function refetchReport(): void {
  store.fetchReport(repositoryId)
}

function refetchRoadmap(): void {
  store.fetchRoadmap(repositoryId)
}

onMounted(() => {
  refetchReport()
  refetchRoadmap()
})
</script>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run RepositoryDetailView`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/views/RepositoryDetailView.vue radar-dashboard/src/views/__tests__/RepositoryDetailView.spec.ts
git commit -m "feat(radar-dashboard): add RepositoryDetailView with report and roadmap tabs"
```

---

### Task 13: `SettingsView.vue`

**Files:**
- Create: `radar-dashboard/src/views/SettingsView.vue`
- Test: `radar-dashboard/src/views/__tests__/SettingsView.spec.ts`

**Interfaces:**
- Consumes: `useApiKeyStore` (Task 4)
- Produces: `SettingsView.vue` (mounted at `/settings` in Task 14)

- [ ] **Step 1: Write the failing tests**

```typescript
// radar-dashboard/src/views/__tests__/SettingsView.spec.ts
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { useApiKeyStore } from '@/stores/apiKey'
import SettingsView from '../SettingsView.vue'

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('pre-fills the input with the currently stored key', () => {
    useApiKeyStore().setApiKey('existing-key')

    const wrapper = mount(SettingsView)

    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('existing-key')
  })

  it('saves the typed key to the store and shows confirmation', async () => {
    const store = useApiKeyStore()
    const wrapper = mount(SettingsView)

    await wrapper.find('input').setValue('new-key')
    await wrapper.find('button').trigger('click')

    expect(store.apiKey).toBe('new-key')
    expect(wrapper.text()).toContain('Saved')
  })
})
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-dashboard && npm run test:unit -- --run SettingsView`
Expected: FAIL (`../SettingsView.vue` does not exist)

- [ ] **Step 3: Implement the view**

```vue
<!-- radar-dashboard/src/views/SettingsView.vue -->
<template>
  <div class="settings-view">
    <h1>Settings</h1>
    <label>
      API key
      <input v-model="draft" type="password" autocomplete="off" />
    </label>
    <button type="button" @click="save">Save</button>
    <p v-if="saved">Saved.</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useApiKeyStore } from '@/stores/apiKey'

const store = useApiKeyStore()
const draft = ref(store.apiKey)
const saved = ref(false)

function save(): void {
  store.setApiKey(draft.value)
  saved.value = true
}
</script>
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run SettingsView`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-dashboard/src/views/SettingsView.vue radar-dashboard/src/views/__tests__/SettingsView.spec.ts
git commit -m "feat(radar-dashboard): add SettingsView for the API key"
```

---

### Task 14: Router wiring and the App navigation shell

**Files:**
- Create: `radar-dashboard/src/router/index.ts`
- Modify: `radar-dashboard/src/main.ts`
- Modify: `radar-dashboard/src/App.vue`
- Modify: `radar-dashboard/src/__tests__/App.spec.ts`

**Interfaces:**
- Consumes: `RepositoryListView.vue` (Task 11), `RepositoryDetailView.vue` (Task 12),
  `SettingsView.vue` (Task 13)
- Produces: the mounted app — this is the last task before the app is a working whole

**Design note:** this replaces Task 3's placeholder `App.vue`/`main.ts` and their smoke test with
real navigation. The smoke test's assertion ("renders `radar-dashboard`") moves to asserting the
header link's text instead of a bare heading.

- [ ] **Step 1: Write the failing test**

Replace `radar-dashboard/src/__tests__/App.spec.ts`:

```typescript
// radar-dashboard/src/__tests__/App.spec.ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../App.vue'
import RepositoryListView from '../views/RepositoryListView.vue'
import RepositoryDetailView from '../views/RepositoryDetailView.vue'
import SettingsView from '../views/SettingsView.vue'

async function mountApp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: RepositoryListView },
      { path: '/repositories/:id', component: RepositoryDetailView },
      { path: '/settings', component: SettingsView },
    ],
  })
  router.push('/')
  await router.isReady()
  return mount(App, { global: { plugins: [router] } })
}

describe('App', () => {
  it('renders the radar-dashboard header link', async () => {
    const wrapper = await mountApp()

    expect(wrapper.text()).toContain('radar-dashboard')
  })

  it('navigates to Settings via the header link', async () => {
    const wrapper = await mountApp()

    await wrapper.get('a[href="/settings"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(SettingsView).exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `cd radar-dashboard && npm run test:unit -- --run App`
Expected: FAIL (`App.vue` has no `<RouterView>`/links yet, mounting without a router plugin
present previously — this now requires `router/index.ts` and real views)

- [ ] **Step 3: Create `router/index.ts`**

```typescript
// radar-dashboard/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import RepositoryListView from '@/views/RepositoryListView.vue'
import RepositoryDetailView from '@/views/RepositoryDetailView.vue'
import SettingsView from '@/views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'repository-list', component: RepositoryListView },
    { path: '/repositories/:id', name: 'repository-detail', component: RepositoryDetailView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})

export default router
```

- [ ] **Step 4: Replace `App.vue`**

```vue
<!-- radar-dashboard/src/App.vue -->
<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <RouterLink to="/">radar-dashboard</RouterLink>
      <RouterLink to="/settings">Settings</RouterLink>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
```

- [ ] **Step 5: Wire the router into `main.ts`**

```typescript
// radar-dashboard/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `cd radar-dashboard && npm run test:unit -- --run`
Expected: PASS (full suite, every task's tests included)

- [ ] **Step 7: Confirm type-checking and linting still run clean**

Run: `cd radar-dashboard && npm run type-check && npm run lint`
Expected: PASS, no errors

- [ ] **Step 8: Commit**

```bash
git add radar-dashboard/src/router/index.ts radar-dashboard/src/main.ts radar-dashboard/src/App.vue radar-dashboard/src/__tests__/App.spec.ts
git commit -m "feat(radar-dashboard): wire router and navigation shell"
```

---

### Task 15: Docker deployment and Traefik `/api` proxy

**Files:**
- Create: `radar-dashboard/Dockerfile`
- Create: `radar-dashboard/nginx.conf`
- Modify: `docker-compose.yml`

**Interfaces:** none (deployment-only task, no application code)

- [ ] **Step 1: Write `radar-dashboard/nginx.conf`**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;
    gzip_min_length 256;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Write `radar-dashboard/Dockerfile`**

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 3: Update `docker-compose.yml`**

Modify the `radar-api` service's `labels` to add the `/api`-prefixed router (existing
`radar-api` labels stay, these are added alongside them), and fill in the `radar-dashboard`
service that was previously commented out:

```yaml
services:
  radar-api:
    build:
      context: .
      dockerfile: radar-api/Dockerfile
    environment:
      - RADAR_DATABASE_URL=sqlite:////data/radar.db
      - RADAR_API_KEY=${RADAR_API_KEY}
    volumes:
      - radar-data:/data
    ports:
      - "8000:8000"
    networks:
      - traefik-public
      - default
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.radar-api.rule=Host(`radar-api.marvinlerouge.local`)"
      - "traefik.http.routers.radar-api.entrypoints=web"
      - "traefik.http.services.radar-api.loadbalancer.server.port=8000"
      - "traefik.http.routers.radar-api-proxied.rule=Host(`radar.marvinlerouge.local`) && PathPrefix(`/api`)"
      - "traefik.http.routers.radar-api-proxied.entrypoints=web"
      - "traefik.http.middlewares.radar-api-strip.stripprefix.prefixes=/api"
      - "traefik.http.routers.radar-api-proxied.middlewares=radar-api-strip"
      - "traefik.http.routers.radar-api-proxied.service=radar-api"

  radar-audit:
    build:
      context: .
      dockerfile: radar-audit/Dockerfile
    environment:
      - RADAR_DATABASE_URL=sqlite:////data/radar.db
    volumes:
      - radar-data:/data
      - ${RADAR_PORTFOLIO_PATH:-./portfolio}:/portfolio:ro
    profiles: ["cli"]

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

volumes:
  radar-data:

networks:
  traefik-public:
    external: true
```

- [ ] **Step 4: Validate the compose file parses**

Run: `RADAR_API_KEY=x docker compose config`
Expected: prints the resolved compose configuration with no errors

- [ ] **Step 5: Build the `radar-dashboard` image**

Run: `docker compose build radar-dashboard`
Expected: image builds successfully

- [ ] **Step 6: Commit**

```bash
git add radar-dashboard/Dockerfile radar-dashboard/nginx.conf docker-compose.yml
git commit -m "feat(radar-dashboard): add Docker deployment and Traefik /api proxy"
```

---

### Task 16: Full verification

**Files:** none created; verification only.

- [ ] **Step 1: Run the full `radar-dashboard` test suite**

Run: `cd radar-dashboard && npm run test:unit -- --run`
Expected: PASS, zero failures (every task's tests: Tasks 3-14)

- [ ] **Step 2: Run type-checking and linting**

Run: `cd radar-dashboard && npm run type-check && npm run lint`
Expected: PASS, no errors

- [ ] **Step 3: Run the full `radar-api` suite and static checks**

Run: `cd radar-api && uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: PASS, no errors (includes Tasks 1-2's new tests)

- [ ] **Step 4: Run the full monorepo test suite to confirm no regression**

Run: `uv run pytest` (from repo root)
Expected: PASS, same pass count as before this plan plus Tasks 1-2's new `radar-api` tests

- [ ] **Step 5: Commit any final formatting fixes**

```bash
git add -u
git commit -m "chore(radar-dashboard): apply formatting fixes"
```

(Skip this step entirely if Steps 1-4 made no changes — no empty commits.)
