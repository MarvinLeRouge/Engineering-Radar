# Minimal radar-api Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** stand up `radar-api`, a minimal FastAPI service exposing read endpoints over the
existing `radar-core` data model plus 3 narrow, human-confirmed-only write endpoints, so report
data can be served without ever writing into an audited repo.

**Architecture:** a new `uv` workspace member (`radar-api/`) alongside `radar-core`/`radar-audit`.
Synchronous FastAPI, no service layer: each endpoint opens a DB session via
`radar_core.db.get_engine`/`get_session`, runs a direct SQLModel `select()`, and returns a flat
Pydantic projection. A single static API key (`X-API-Key` header) gates the 3 write endpoints only.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, SQLModel (via `radar-core`), Pydantic v2, pytest +
`httpx`/`TestClient`, Alembic (migrations already exist in `radar-core`, none new needed here).

**Spec:** `docs/superpowers/specs/2026-09-29-minimal-radar-api-design.md`

## Global Constraints

- `radar-api` is a new `uv` workspace member depending on `radar-core` via `[tool.uv.sources]` workspace reference, `requires-python = ">=3.12"`.
- `RADAR_DATABASE_URL` and `RADAR_API_KEY` must both be set explicitly; no implicit default location for either (mirrors `radar_audit.cli._database_url()`'s convention).
- Exactly 3 write endpoints exist (`PATCH /findings/{id}/verdict`, `PATCH /findings/{id}/status`, `PATCH /roadmap-items/{id}/status`); every other endpoint is read-only. No broad CRUD surface.
- Write endpoints require the `X-API-Key` header, checked with `secrets.compare_digest`; read endpoints stay open.
- `RoadmapItem` transitioning to `DONE` structurally requires `done_evidence_id` in the request body (Pydantic validation, not a downstream check).
- No caching, no intermediate service layer: one DB session per request via `Depends(get_db_session)`.
- `ruff` (line-length 100, target py312) and `mypy --strict` must pass for `radar-api`, same as `radar-core`/`radar-audit` (see root `pyproject.toml`).

## Review Focus

1. A write request with a syntactically valid JSON body but a value outside the target enum (e.g. `{"status": "CLOSED"}`) must return `422`, not `500` or a silent no-op.
2. A write request repeating the resource's current value (e.g. `status` already `RESOLVED`) must be rejected with `400`, not silently accepted as if a transition happened.
3. A badge request for a repository whose `ScoringRun` exists but whose `global_score` is `None` must not crash formatting a `None` float; it must fall back to the "not yet audited" shape.
4. `GET .../findings` and `GET .../roadmap` must return `404` when the repository id itself doesn't exist, but `200` with an empty array when the repository exists with nothing to list — these two "nothing here" cases must stay distinguishable.
5. `require_api_key` must reject a missing (`None`) header the same way it rejects a wrong string, without raising an unhandled `TypeError` from `secrets.compare_digest` (which requires two strings).

---

### Task 1: Package scaffolding and configuration

**Files:**
- Create: `radar-api/pyproject.toml`
- Create: `radar-api/src/radar_api/__init__.py`
- Create: `radar-api/src/radar_api/config.py`
- Modify: `pyproject.toml:2` (root workspace members list)
- Test: `radar-api/tests/test_config.py`
- Test: `radar-api/tests/__init__.py` (not needed — pytest discovers by path, no package init required for the tests dir)

**Interfaces:**
- Produces: `radar_api.config.get_database_url() -> str`, `radar_api.config.get_api_key() -> str`, `radar_api.config.MissingDatabaseUrlError`, `radar_api.config.MissingApiKeyError`

- [ ] **Step 1: Register the workspace member**

Modify `pyproject.toml`:

```toml
[tool.uv.workspace]
members = ["radar-core", "radar-audit", "radar-api"]
```

- [ ] **Step 2: Create `radar-api/pyproject.toml`**

```toml
[project]
name = "radar-api"
version = "0.1.0"
description = "Minimal read/write API for Engineering-Radar."
requires-python = ">=3.12"
dependencies = [
    "radar-core",
    "fastapi>=0.115",
    "uvicorn>=0.30",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.6",
    "mypy>=1.11",
]

[tool.uv.sources]
radar-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/radar_api"]
```

- [ ] **Step 3: Create the package skeleton**

```bash
mkdir -p radar-api/src/radar_api/schemas radar-api/src/radar_api/routers radar-api/tests
touch radar-api/src/radar_api/__init__.py
touch radar-api/src/radar_api/schemas/__init__.py
touch radar-api/src/radar_api/routers/__init__.py
```

- [ ] **Step 4: Write the failing test for `config.py`**

```python
# radar-api/tests/test_config.py
import pytest

from radar_api.config import (
    MissingApiKeyError,
    MissingDatabaseUrlError,
    get_api_key,
    get_database_url,
)


def test_get_database_url_raises_when_unset(monkeypatch):
    monkeypatch.delenv("RADAR_DATABASE_URL", raising=False)
    with pytest.raises(MissingDatabaseUrlError):
        get_database_url()


def test_get_database_url_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("RADAR_DATABASE_URL", "sqlite:///test.db")
    assert get_database_url() == "sqlite:///test.db"


def test_get_api_key_raises_when_unset(monkeypatch):
    monkeypatch.delenv("RADAR_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        get_api_key()


def test_get_api_key_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    assert get_api_key() == "secret"
```

- [ ] **Step 5: Run it, confirm it fails**

Run: `cd radar-api && uv run pytest tests/test_config.py -v`
Expected: FAIL (collection error — `radar_api.config` does not exist yet)

- [ ] **Step 6: Implement `config.py`**

```python
# radar-api/src/radar_api/config.py
from __future__ import annotations

import os


class MissingDatabaseUrlError(RuntimeError):
    """Raised when RADAR_DATABASE_URL is not set."""


class MissingApiKeyError(RuntimeError):
    """Raised when RADAR_API_KEY is not set."""


def get_database_url() -> str:
    url = os.environ.get("RADAR_DATABASE_URL")
    if not url:
        raise MissingDatabaseUrlError(
            "RADAR_DATABASE_URL must be set explicitly; radar-api never assumes "
            "a default database location."
        )
    return url


def get_api_key() -> str:
    key = os.environ.get("RADAR_API_KEY")
    if not key:
        raise MissingApiKeyError(
            "RADAR_API_KEY must be set explicitly; radar-api never assumes a default API key."
        )
    return key
```

- [ ] **Step 7: Run tests, confirm they pass**

Run: `cd radar-api && uv sync && uv run pytest tests/test_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml radar-api/pyproject.toml radar-api/src radar-api/tests
git commit -m "feat(radar-api): scaffold package and required env-var config"
```

---

### Task 2: App wiring, DB session dependency, and test infrastructure

**Files:**
- Create: `radar-api/src/radar_api/main.py`
- Create: `radar-api/src/radar_api/dependencies.py`
- Create: `radar-api/tests/conftest.py`
- Test: `radar-api/tests/test_dependencies.py`
- Test: `radar-api/tests/test_main.py`

**Interfaces:**
- Consumes: `radar_api.config.get_database_url` (Task 1), `radar_core.db.get_engine`/`get_session`
- Produces: `radar_api.dependencies.get_db_session` (generator dependency, used by every router task from here on), `radar_api.main.app` (the `FastAPI` instance every router is mounted onto), `db_session`/`client` pytest fixtures (used by every subsequent test file)

- [ ] **Step 1: Write the failing test for `get_db_session`**

```python
# radar-api/tests/test_dependencies.py
import pytest
from sqlmodel import Session

from radar_api.dependencies import get_db_session


def test_get_db_session_yields_a_session_and_closes_it(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{db_path}")

    generator = get_db_session()
    session = next(generator)
    assert isinstance(session, Session)

    with pytest.raises(StopIteration):
        next(generator)
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `cd radar-api && uv run pytest tests/test_dependencies.py -v`
Expected: FAIL (`radar_api.dependencies` does not exist)

- [ ] **Step 3: Implement `dependencies.py`**

```python
# radar-api/src/radar_api/dependencies.py
from __future__ import annotations

from collections.abc import Generator

from radar_core.db import get_engine, get_session
from sqlmodel import Session

from radar_api.config import get_database_url


def get_db_session() -> Generator[Session, None, None]:
    engine = get_engine(get_database_url())
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
```

- [ ] **Step 4: Run test, confirm it passes**

Run: `cd radar-api && uv run pytest tests/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Implement `main.py`**

```python
# radar-api/src/radar_api/main.py
from fastapi import FastAPI

app = FastAPI(title="radar-api")
```

- [ ] **Step 6: Write `conftest.py`**

```python
# radar-api/tests/conftest.py
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from radar_core.db import get_engine
from sqlmodel import Session

from radar_api.dependencies import get_db_session
from radar_api.main import app

RADAR_CORE_ROOT = Path(__file__).resolve().parents[2] / "radar-core"
ALEMBIC_INI = RADAR_CORE_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = RADAR_CORE_ROOT / "alembic"


def _run_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    previous_url = os.environ.get("RADAR_DATABASE_URL")
    os.environ["RADAR_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_url is None:
            del os.environ["RADAR_DATABASE_URL"]
        else:
            os.environ["RADAR_DATABASE_URL"] = previous_url


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    _run_migrations(database_url)

    engine = get_engine(database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    def _override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 7: Write the failing test for the app/client wiring**

```python
# radar-api/tests/test_main.py
def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
```

- [ ] **Step 8: Run it, confirm it fails**

Run: `cd radar-api && uv run pytest tests/test_main.py -v`
Expected: FAIL (`ModuleNotFoundError` for `alembic`/`fastapi` extras not yet synced, or the fixture
chain erroring) — re-run `uv sync` first if the failure is a missing dependency rather than an
assertion failure.

- [ ] **Step 9: Run again after `uv sync`, confirm it passes**

Run: `cd radar-api && uv sync && uv run pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 10: Run the full `radar-api` suite so far**

Run: `cd radar-api && uv run pytest -v`
Expected: PASS (6 tests: 4 from Task 1, 1 from Step 4 above, 1 from Step 9)

- [ ] **Step 11: Commit**

```bash
git add radar-api/src/radar_api/main.py radar-api/src/radar_api/dependencies.py radar-api/tests/conftest.py radar-api/tests/test_dependencies.py radar-api/tests/test_main.py
git commit -m "feat(radar-api): wire FastAPI app, DB session dependency, and test fixtures"
```

---

### Task 3: API key authentication

**Files:**
- Create: `radar-api/src/radar_api/auth.py`
- Test: `radar-api/tests/test_auth.py`

**Interfaces:**
- Consumes: `radar_api.config.get_api_key` (Task 1)
- Produces: `radar_api.auth.require_api_key(x_api_key: str | None) -> None` (raises `fastapi.HTTPException`) — used as a route `dependencies=[Depends(require_api_key)]` entry by every write endpoint from Task 8 onward

- [ ] **Step 1: Write the failing tests**

```python
# radar-api/tests/test_auth.py
import pytest
from fastapi import HTTPException

from radar_api.auth import require_api_key


def test_require_api_key_raises_when_missing(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None)

    assert exc_info.value.status_code == 401


def test_require_api_key_raises_when_wrong(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong")

    assert exc_info.value.status_code == 401


def test_require_api_key_passes_when_correct(monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    require_api_key(x_api_key="secret")
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_auth.py -v`
Expected: FAIL (`radar_api.auth` does not exist)

- [ ] **Step 3: Implement `auth.py`**

```python
# radar-api/src/radar_api/auth.py
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from radar_api.config import get_api_key


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_api_key()
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
        )
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_auth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-api/src/radar_api/auth.py radar-api/tests/test_auth.py
git commit -m "feat(radar-api): add static API-key authentication dependency"
```

---

### Task 4: Repositories router — list and detail

**Files:**
- Create: `radar-api/src/radar_api/schemas/repositories.py`
- Create: `radar-api/src/radar_api/routers/repositories.py`
- Modify: `radar-api/src/radar_api/main.py`
- Test: `radar-api/tests/test_repositories.py`

**Interfaces:**
- Consumes: `radar_api.dependencies.get_db_session` (Task 2)
- Produces: `radar_api.schemas.repositories.RepositoryRead`, `radar_api.routers.repositories.router` (an `APIRouter` mounted in `main.py`; later tasks 5, 6 add more routes onto this same router), `radar_api.routers.repositories._latest_scoring_run(session, repository_id) -> ScoringRun | None` (reused by Tasks 5 and 6)

- [ ] **Step 1: Write the failing tests**

```python
# radar-api/tests/test_repositories.py
from radar_core.models.audit import Audit
from radar_core.models.methodology import MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_scoring_run(db_session, repository, global_score):
    audit = Audit(repository_id=repository.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}-{global_score}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(
        audit_id=audit.id,
        methodology_version_id=methodology_version.id,
        global_score=global_score,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)
    return scoring_run


def test_list_repositories_returns_not_yet_audited_when_no_scoring_run(client, db_session):
    _make_repository(db_session, "repo-a")

    response = client.get("/repositories")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["audit_status"] == "not_yet_audited"
    assert body[0]["global_score"] is None


def test_list_repositories_returns_global_score_when_scored(client, db_session):
    repo = _make_repository(db_session, "repo-b")
    _make_scoring_run(db_session, repo, global_score=7.5)

    response = client.get("/repositories")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["audit_status"] == "scored"
    assert body[0]["global_score"] == 7.5


def test_get_repository_returns_404_when_missing(client):
    response = client.get("/repositories/999")

    assert response.status_code == 404


def test_get_repository_returns_detail(client, db_session):
    repo = _make_repository(db_session, "repo-c")

    response = client.get(f"/repositories/{repo.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "repo-c"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_repositories.py -v`
Expected: FAIL (`radar_api.routers.repositories` does not exist)

- [ ] **Step 3: Implement the schema**

```python
# radar-api/src/radar_api/schemas/repositories.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RepositoryRead(BaseModel):
    id: int
    name: str
    path: str
    global_score: float | None
    audit_status: Literal["scored", "not_yet_audited"]
```

- [ ] **Step 4: Implement the router**

```python
# radar-api/src/radar_api/routers/repositories.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.repositories import RepositoryRead

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _latest_scoring_run(session: Session, repository_id: int) -> ScoringRun | None:
    return session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()


def _to_repository_read(session: Session, repository: Repository) -> RepositoryRead:
    assert repository.id is not None
    scoring_run = _latest_scoring_run(session, repository.id)
    return RepositoryRead(
        id=repository.id,
        name=repository.name,
        path=repository.path,
        global_score=scoring_run.global_score if scoring_run else None,
        audit_status="scored" if scoring_run is not None else "not_yet_audited",
    )


@router.get("", response_model=list[RepositoryRead])
def list_repositories(session: Session = Depends(get_db_session)) -> list[RepositoryRead]:
    repositories = session.exec(select(Repository)).all()
    return [_to_repository_read(session, repo) for repo in repositories]


@router.get("/{repository_id}", response_model=RepositoryRead)
def get_repository(
    repository_id: int, session: Session = Depends(get_db_session)
) -> RepositoryRead:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return _to_repository_read(session, repository)
```

- [ ] **Step 5: Mount the router**

```python
# radar-api/src/radar_api/main.py
from fastapi import FastAPI

from radar_api.routers import repositories

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_repositories.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add radar-api/src/radar_api/schemas/repositories.py radar-api/src/radar_api/routers/repositories.py radar-api/src/radar_api/main.py radar-api/tests/test_repositories.py
git commit -m "feat(radar-api): add GET /repositories and GET /repositories/{id}"
```

---

### Task 5: Repositories router — full report

**Files:**
- Create: `radar-api/src/radar_api/schemas/report.py`
- Modify: `radar-api/src/radar_api/routers/repositories.py`
- Modify: `radar-api/tests/test_repositories.py`

**Interfaces:**
- Consumes: `_latest_scoring_run` (Task 4)
- Produces: `radar_api.schemas.report.RepositoryReport` (also consumed conceptually by items D/E later, outside this plan's scope)

- [ ] **Step 1: Write the failing tests**

Append to `radar-api/tests/test_repositories.py`:

```python
from radar_core.enums import Confidence, FindingSeverity, ScoreLevel, ScoringModel
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion
from radar_core.models.scoring import Score


def _seed_category_and_criterion(db_session, methodology_version_id, name="Dependency vulns"):
    category = Category(
        methodology_version_id=methodology_version_id, name="Security", weight=1.0, order=1
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name=name,
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)
    return category, criterion


def test_get_repository_report_returns_404_when_no_score(client, db_session):
    repo = _make_repository(db_session, "repo-no-score")

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 404


def test_get_repository_report_includes_findings_and_recommendations(client, db_session):
    repo = _make_repository(db_session, "repo-with-findings")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    category, criterion = _seed_category_and_criterion(
        db_session, scoring_run.methodology_version_id
    )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=4.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(score)
    db_session.commit()

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.HIGH,
        description="a vulnerable dependency",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    db_session.add(Recommendation(finding_id=finding.id, text="upgrade the dependency"))
    db_session.commit()

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    body = response.json()
    criterion_report = body["categories"][0]["criteria"][0]
    assert criterion_report["status"] == "scored"
    assert criterion_report["value"] == 4.0
    assert criterion_report["findings"][0]["recommendation"] == "upgrade the dependency"


def test_get_repository_report_marks_unscored_criterion_as_not_yet_audited(client, db_session):
    repo = _make_repository(db_session, "repo-partial")
    scoring_run = _make_scoring_run(db_session, repo, global_score=5.0)
    _seed_category_and_criterion(db_session, scoring_run.methodology_version_id)

    response = client.get(f"/repositories/{repo.id}/report")

    assert response.status_code == 200
    criterion_report = response.json()["categories"][0]["criteria"][0]
    assert criterion_report["status"] == "not_yet_audited"
    assert criterion_report["value"] is None
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_repositories.py -v -k report`
Expected: FAIL (404 on an endpoint that doesn't exist yet)

- [ ] **Step 3: Implement the schema**

```python
# radar-api/src/radar_api/schemas/report.py
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FindingReport(BaseModel):
    id: int
    severity: str
    description: str
    file: str | None
    line: int | None
    status: str
    human_verdict: str
    recommendation: str | None


class CriterionReport(BaseModel):
    id: int
    name: str
    status: Literal["scored", "not_applicable", "not_yet_audited"]
    value: float | None
    na_reason: str | None
    findings: list[FindingReport]


class CategoryReport(BaseModel):
    id: int
    name: str
    order: int
    status: Literal["scored", "not_yet_audited"]
    value: float | None
    confidence: str | None
    criteria: list[CriterionReport]


class RepositoryReport(BaseModel):
    repository_id: int
    repository_name: str
    commit_sha: str
    audited_at: datetime
    scored_at: datetime
    categories: list[CategoryReport]
```

- [ ] **Step 4: Add the route**

Add to `radar-api/src/radar_api/routers/repositories.py` (new imports at the top, new function at
the bottom):

```python
from radar_core.enums import ScoreLevel
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion
from radar_core.models.scoring import Score

from radar_api.schemas.report import CategoryReport, CriterionReport, FindingReport, RepositoryReport
```

```python
@router.get("/{repository_id}/report", response_model=RepositoryReport)
def get_repository_report(
    repository_id: int, session: Session = Depends(get_db_session)
) -> RepositoryReport:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    scoring_run = _latest_scoring_run(session, repository_id)
    if scoring_run is None:
        raise HTTPException(status_code=404, detail="no score found for this repository")

    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None

    categories = session.exec(
        select(Category)
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(Category.order)  # type: ignore[arg-type]
    ).all()

    scores = session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    category_scores = {s.category_id: s for s in scores if s.level == ScoreLevel.CATEGORY}
    criterion_scores = {s.criterion_id: s for s in scores if s.level == ScoreLevel.CRITERION}

    findings = session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    findings_by_criterion: dict[int | None, list[Finding]] = {}
    for finding in findings:
        findings_by_criterion.setdefault(finding.criterion_id, []).append(finding)

    finding_ids = [f.id for f in findings if f.id is not None]
    recommendations = session.exec(
        select(Recommendation).where(Recommendation.finding_id.in_(finding_ids))  # type: ignore[attr-defined]
    ).all()
    recommendation_by_finding = {r.finding_id: r.text for r in recommendations}

    category_reports = []
    for category in categories:
        category_score = category_scores.get(category.id)
        criteria = session.exec(
            select(Criterion).where(Criterion.category_id == category.id).order_by(Criterion.id)  # type: ignore[arg-type]
        ).all()
        criterion_reports = []
        for criterion in criteria:
            criterion_score = criterion_scores.get(criterion.id)
            if criterion_score is None:
                criterion_status = "not_yet_audited"
            elif criterion_score.na_reason is not None:
                criterion_status = "not_applicable"
            else:
                criterion_status = "scored"

            finding_reports = [
                FindingReport(
                    id=f.id,  # type: ignore[arg-type]
                    severity=f.severity.value,
                    description=f.description,
                    file=f.file,
                    line=f.line,
                    status=f.status.value,
                    human_verdict=f.human_verdict.value,
                    recommendation=recommendation_by_finding.get(f.id),
                )
                for f in findings_by_criterion.get(criterion.id, [])
            ]
            criterion_reports.append(
                CriterionReport(
                    id=criterion.id,  # type: ignore[arg-type]
                    name=criterion.name,
                    status=criterion_status,
                    value=criterion_score.value if criterion_score else None,
                    na_reason=criterion_score.na_reason if criterion_score else None,
                    findings=finding_reports,
                )
            )
        category_reports.append(
            CategoryReport(
                id=category.id,  # type: ignore[arg-type]
                name=category.name,
                order=category.order,
                status="scored" if category_score is not None else "not_yet_audited",
                value=category_score.value if category_score else None,
                confidence=category_score.confidence.value if category_score else None,
                criteria=criterion_reports,
            )
        )

    return RepositoryReport(
        repository_id=repository.id,  # type: ignore[arg-type]
        repository_name=repository.name,
        commit_sha=audit.commit_sha,
        audited_at=audit.audited_at,
        scored_at=scoring_run.scored_at,
        categories=category_reports,
    )
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_repositories.py -v`
Expected: PASS (7 tests total)

- [ ] **Step 6: Commit**

```bash
git add radar-api/src/radar_api/schemas/report.py radar-api/src/radar_api/routers/repositories.py radar-api/tests/test_repositories.py
git commit -m "feat(radar-api): add GET /repositories/{id}/report"
```

---

### Task 6: Repositories router — badge

**Files:**
- Create: `radar-api/src/radar_api/schemas/badge.py`
- Modify: `radar-api/src/radar_api/routers/repositories.py`
- Modify: `radar-api/tests/test_repositories.py`

**Interfaces:**
- Consumes: `_latest_scoring_run` (Task 4)
- Produces: `radar_api.schemas.badge.BadgeResponse` (feeds item D, out of this plan's scope)

- [ ] **Step 1: Write the failing tests**

Append to `radar-api/tests/test_repositories.py`:

```python
def test_badge_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/badge")

    assert response.status_code == 404


def test_badge_shows_not_yet_audited_when_no_scoring_run(client, db_session):
    repo = _make_repository(db_session, "repo-badge-unscored")

    response = client.get(f"/repositories/{repo.id}/badge")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "not yet audited"
    assert body["color"] == "lightgrey"
    assert body["schemaVersion"] == 1


def test_badge_shows_not_yet_audited_when_global_score_is_none(client, db_session):
    repo = _make_repository(db_session, "repo-badge-null-score")
    _make_scoring_run(db_session, repo, global_score=None)

    response = client.get(f"/repositories/{repo.id}/badge")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "not yet audited"
    assert body["color"] == "lightgrey"


def test_badge_color_reflects_global_score(client, db_session):
    repo = _make_repository(db_session, "repo-badge-high-score")
    _make_scoring_run(db_session, repo, global_score=8.5)

    response = client.get(f"/repositories/{repo.id}/badge")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "8.5/10"
    assert body["color"] == "brightgreen"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_repositories.py -v -k badge`
Expected: FAIL (404 on an endpoint that doesn't exist yet)

- [ ] **Step 3: Implement the schema**

```python
# radar-api/src/radar_api/schemas/badge.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BadgeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = Field(default=1, alias="schemaVersion")
    label: str
    message: str
    color: str
```

- [ ] **Step 4: Add the route**

Add to `radar-api/src/radar_api/routers/repositories.py`:

```python
from radar_api.schemas.badge import BadgeResponse

_BADGE_LABEL = "quality"


def _badge_color(score: float) -> str:
    if score >= 8:
        return "brightgreen"
    if score >= 6:
        return "green"
    if score >= 4:
        return "yellow"
    if score >= 2:
        return "orange"
    return "red"


@router.get("/{repository_id}/badge", response_model=BadgeResponse)
def get_repository_badge(
    repository_id: int, session: Session = Depends(get_db_session)
) -> BadgeResponse:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    scoring_run = _latest_scoring_run(session, repository_id)
    if scoring_run is None or scoring_run.global_score is None:
        return BadgeResponse(label=_BADGE_LABEL, message="not yet audited", color="lightgrey")

    return BadgeResponse(
        label=_BADGE_LABEL,
        message=f"{scoring_run.global_score:.1f}/10",
        color=_badge_color(scoring_run.global_score),
    )
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_repositories.py -v`
Expected: PASS (11 tests total)

- [ ] **Step 6: Commit**

```bash
git add radar-api/src/radar_api/schemas/badge.py radar-api/src/radar_api/routers/repositories.py radar-api/tests/test_repositories.py
git commit -m "feat(radar-api): add GET /repositories/{id}/badge"
```

---

### Task 7: Findings router — list

**Files:**
- Create: `radar-api/src/radar_api/schemas/findings.py`
- Create: `radar-api/src/radar_api/routers/findings.py`
- Modify: `radar-api/src/radar_api/main.py`
- Test: `radar-api/tests/test_findings.py`

**Interfaces:**
- Consumes: `radar_api.dependencies.get_db_session` (Task 2), `_latest_scoring_run` pattern (same
  join logic as Task 4, duplicated locally since it is repository->audit->scoring_run scoped
  differently here — filtered by repository, not returning a single latest run)
- Produces: `radar_api.schemas.findings.FindingRead`, `radar_api.routers.findings.router` (later
  Tasks 8-9 add write routes onto this same router), `radar_api.routers.findings._to_finding_read`
  (reused by Tasks 8-9)

**Design note:** the list scopes to findings from the repository's *latest* `ScoringRun` only
(same scope as the `/report` endpoint in Task 5), so the triage view matches what `/report` shows
instead of accumulating findings across every historical re-audit.

- [ ] **Step 1: Write the failing tests**

```python
# radar-api/tests/test_findings.py
from radar_core.enums import Confidence, FindingSeverity, FindingStatus, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.methodology import Category, Criterion
from radar_core.models.methodology import MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_scoring_run(db_session, repository):
    audit = Audit(repository_id=repository.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)
    return scoring_run


def _make_criterion(db_session, methodology_version_id):
    category = Category(
        methodology_version_id=methodology_version_id, name="Security", weight=1.0, order=1
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="SAST findings",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)
    return criterion


def _make_finding(db_session, scoring_run, criterion, severity=FindingSeverity.HIGH, status=FindingStatus.OPEN):
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=severity,
        description="issue",
        confidence=Confidence.HIGH,
        status=status,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_list_findings_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/findings")

    assert response.status_code == 404


def test_list_findings_returns_empty_list_when_none(client, db_session):
    repo = _make_repository(db_session, "repo-no-findings")

    response = client.get(f"/repositories/{repo.id}/findings")

    assert response.status_code == 200
    assert response.json() == []


def test_list_findings_returns_findings_for_latest_scoring_run(client, db_session):
    repo = _make_repository(db_session, "repo-findings")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    _make_finding(db_session, scoring_run, criterion)

    response = client.get(f"/repositories/{repo.id}/findings")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["severity"] == "HIGH"


def test_list_findings_filters_by_status(client, db_session):
    repo = _make_repository(db_session, "repo-findings-filter")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    _make_finding(db_session, scoring_run, criterion, status=FindingStatus.OPEN)
    _make_finding(db_session, scoring_run, criterion, status=FindingStatus.RESOLVED)

    response = client.get(f"/repositories/{repo.id}/findings", params={"status": "RESOLVED"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "RESOLVED"


def test_list_findings_filters_by_severity(client, db_session):
    repo = _make_repository(db_session, "repo-findings-severity")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    _make_finding(db_session, scoring_run, criterion, severity=FindingSeverity.CRITICAL)
    _make_finding(db_session, scoring_run, criterion, severity=FindingSeverity.LOW)

    response = client.get(f"/repositories/{repo.id}/findings", params={"severity": "CRITICAL"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["severity"] == "CRITICAL"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_findings.py -v`
Expected: FAIL (`radar_api.routers.findings` does not exist)

- [ ] **Step 3: Implement the schema**

```python
# radar-api/src/radar_api/schemas/findings.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from radar_core.enums import FindingStatus, HumanVerdict


class FindingRead(BaseModel):
    id: int
    criterion_id: int
    severity: str
    description: str
    file: str | None
    line: int | None
    status: str
    human_verdict: str
    detected_at: datetime


class FindingVerdictUpdate(BaseModel):
    human_verdict: HumanVerdict


class FindingStatusUpdate(BaseModel):
    status: FindingStatus
```

- [ ] **Step 4: Implement the router**

```python
# radar-api/src/radar_api/routers/findings.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from radar_core.enums import FindingSeverity, FindingStatus
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.findings import FindingRead

router = APIRouter(tags=["findings"])


def _to_finding_read(finding: Finding) -> FindingRead:
    assert finding.id is not None
    return FindingRead(
        id=finding.id,
        criterion_id=finding.criterion_id,
        severity=finding.severity.value,
        description=finding.description,
        file=finding.file,
        line=finding.line,
        status=finding.status.value,
        human_verdict=finding.human_verdict.value,
        detected_at=finding.detected_at,
    )


@router.get("/repositories/{repository_id}/findings", response_model=list[FindingRead])
def list_findings(
    repository_id: int,
    status_filter: FindingStatus | None = Query(default=None, alias="status"),
    severity: FindingSeverity | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[FindingRead]:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    latest_scoring_run = session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()
    if latest_scoring_run is None:
        return []

    query = select(Finding).where(Finding.scoring_run_id == latest_scoring_run.id)
    if status_filter is not None:
        query = query.where(Finding.status == status_filter)
    if severity is not None:
        query = query.where(Finding.severity == severity)

    findings = session.exec(query).all()
    return [_to_finding_read(f) for f in findings]
```

- [ ] **Step 5: Mount the router**

```python
# radar-api/src/radar_api/main.py
from fastapi import FastAPI

from radar_api.routers import findings, repositories

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
app.include_router(findings.router)
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_findings.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add radar-api/src/radar_api/schemas/findings.py radar-api/src/radar_api/routers/findings.py radar-api/src/radar_api/main.py radar-api/tests/test_findings.py
git commit -m "feat(radar-api): add GET /repositories/{id}/findings"
```

---

### Task 8: Findings router — update human verdict

**Files:**
- Modify: `radar-api/src/radar_api/schemas/findings.py` (already has `FindingVerdictUpdate` from Task 7, no change needed)
- Modify: `radar-api/src/radar_api/routers/findings.py`
- Modify: `radar-api/tests/test_findings.py`

**Interfaces:**
- Consumes: `radar_api.auth.require_api_key` (Task 3), `_to_finding_read` (Task 7)

- [ ] **Step 1: Write the failing tests**

Append to `radar-api/tests/test_findings.py`:

```python
def test_update_finding_verdict_requires_api_key(client, db_session):
    repo = _make_repository(db_session, "repo-verdict-noauth")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict", json={"human_verdict": "TRUE_POSITIVE"}
    )

    assert response.status_code == 401


def test_update_finding_verdict_returns_404_when_missing(client, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    response = client.patch(
        "/findings/999/verdict",
        json={"human_verdict": "TRUE_POSITIVE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 404


def test_update_finding_verdict_rejects_unknown_enum_value(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-bad-enum")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict",
        json={"human_verdict": "NOT_A_VALUE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 422


def test_update_finding_verdict_rejects_no_op_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-noop")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict",
        json={"human_verdict": "UNREVIEWED"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_finding_verdict_succeeds(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-verdict-ok")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(
        f"/findings/{finding.id}/verdict",
        json={"human_verdict": "TRUE_POSITIVE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["human_verdict"] == "TRUE_POSITIVE"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_findings.py -v -k verdict`
Expected: FAIL (404 on a route that doesn't exist)

- [ ] **Step 3: Add the route**

Add to `radar-api/src/radar_api/routers/findings.py` (new imports at the top, new function at the
bottom):

```python
from radar_api.auth import require_api_key
from radar_api.schemas.findings import FindingVerdictUpdate
```

```python
@router.patch(
    "/findings/{finding_id}/verdict",
    response_model=FindingRead,
    dependencies=[Depends(require_api_key)],
)
def update_finding_verdict(
    finding_id: int,
    payload: FindingVerdictUpdate,
    session: Session = Depends(get_db_session),
) -> FindingRead:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    if finding.human_verdict == payload.human_verdict:
        raise HTTPException(
            status_code=400,
            detail=f"finding already has human_verdict {payload.human_verdict.value}",
        )
    finding.human_verdict = payload.human_verdict
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return _to_finding_read(finding)
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_findings.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Commit**

```bash
git add radar-api/src/radar_api/routers/findings.py radar-api/tests/test_findings.py
git commit -m "feat(radar-api): add PATCH /findings/{id}/verdict"
```

---

### Task 9: Findings router — update status

**Files:**
- Modify: `radar-api/src/radar_api/routers/findings.py`
- Modify: `radar-api/tests/test_findings.py`

**Interfaces:**
- Consumes: `radar_api.auth.require_api_key` (Task 3), `_to_finding_read` (Task 7)

- [ ] **Step 1: Write the failing tests**

Append to `radar-api/tests/test_findings.py`:

```python
def test_update_finding_status_requires_api_key(client, db_session):
    repo = _make_repository(db_session, "repo-status-noauth")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion)

    response = client.patch(f"/findings/{finding.id}/status", json={"status": "RESOLVED"})

    assert response.status_code == 401


def test_update_finding_status_rejects_no_op_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-status-noop")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion, status=FindingStatus.OPEN)

    response = client.patch(
        f"/findings/{finding.id}/status",
        json={"status": "OPEN"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_finding_status_succeeds(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-status-ok")
    scoring_run = _make_scoring_run(db_session, repo)
    criterion = _make_criterion(db_session, scoring_run.methodology_version_id)
    finding = _make_finding(db_session, scoring_run, criterion, status=FindingStatus.OPEN)

    response = client.patch(
        f"/findings/{finding.id}/status",
        json={"status": "WONT_FIX"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "WONT_FIX"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_findings.py -v -k "status and not verdict"`
Expected: FAIL (404 on a route that doesn't exist)

- [ ] **Step 3: Add the route**

Add to `radar-api/src/radar_api/routers/findings.py`:

```python
from radar_api.schemas.findings import FindingStatusUpdate
```

```python
@router.patch(
    "/findings/{finding_id}/status",
    response_model=FindingRead,
    dependencies=[Depends(require_api_key)],
)
def update_finding_status(
    finding_id: int,
    payload: FindingStatusUpdate,
    session: Session = Depends(get_db_session),
) -> FindingRead:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    if finding.status == payload.status:
        raise HTTPException(
            status_code=400,
            detail=f"finding already has status {payload.status.value}",
        )
    finding.status = payload.status
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return _to_finding_read(finding)
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_findings.py -v`
Expected: PASS (13 tests total)

- [ ] **Step 5: Commit**

```bash
git add radar-api/src/radar_api/routers/findings.py radar-api/tests/test_findings.py
git commit -m "feat(radar-api): add PATCH /findings/{id}/status"
```

---

### Task 10: Roadmap router — list

**Files:**
- Create: `radar-api/src/radar_api/schemas/roadmap.py`
- Create: `radar-api/src/radar_api/routers/roadmap.py`
- Modify: `radar-api/src/radar_api/main.py`
- Test: `radar-api/tests/test_roadmap.py`

**Interfaces:**
- Consumes: `radar_api.dependencies.get_db_session` (Task 2)
- Produces: `radar_api.schemas.roadmap.RoadmapItemRead`, `radar_api.routers.roadmap.router` (Task
  11 adds the write route onto this same router), `radar_api.routers.roadmap._to_roadmap_item_read`
  (reused by Task 11)

**Design note:** `RoadmapItem` has no direct `repository_id`. The path is `RoadmapItem ->
ImprovementTask -> FindingImprovementTaskLink -> Finding -> ScoringRun -> Audit -> Repository`.
Listing by repository joins across that chain with `.distinct()`, since one `ImprovementTask` can
link multiple findings.

- [ ] **Step 1: Write the failing tests**

```python
# radar-api/tests/test_roadmap.py
from radar_core.enums import Confidence, FindingSeverity, RoadmapStatus, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun


def _make_repository(db_session, name="repo"):
    repo = Repository(name=name, path=f"/tmp/{name}")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _make_finding_chain(db_session, repository):
    audit = Audit(repository_id=repository.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = MethodologyVersion(version_label=f"v-{repository.id}")
    db_session.add(methodology_version)
    db_session.commit()
    db_session.refresh(methodology_version)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    category = Category(
        methodology_version_id=methodology_version.id, name="Security", weight=1.0, order=1
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="SAST findings",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.HIGH,
        description="issue",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO):
    task = ImprovementTask(title="Fix it", description="...")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=status, priority=1)
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)
    return roadmap_item


def test_list_roadmap_items_returns_404_when_repository_missing(client):
    response = client.get("/repositories/999/roadmap")

    assert response.status_code == 404


def test_list_roadmap_items_returns_empty_list_when_none(client, db_session):
    repo = _make_repository(db_session, "repo-no-roadmap")

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    assert response.json() == []


def test_list_roadmap_items_returns_items_linked_via_findings(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap")
    finding = _make_finding_chain(db_session, repo)
    _make_roadmap_item(db_session, finding)

    response = client.get(f"/repositories/{repo.id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "TODO"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v`
Expected: FAIL (`radar_api.routers.roadmap` does not exist)

- [ ] **Step 3: Implement the schema**

```python
# radar-api/src/radar_api/schemas/roadmap.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator
from radar_core.enums import RoadmapStatus


class RoadmapItemRead(BaseModel):
    id: int
    improvement_task_id: int
    status: str
    priority: int
    estimated_effort: str | None
    estimated_impact: str | None
    promoted_at: datetime
    done_at: datetime | None


class RoadmapItemStatusUpdate(BaseModel):
    status: RoadmapStatus
    done_evidence_id: int | None = None

    @model_validator(mode="after")
    def _require_evidence_for_done(self) -> "RoadmapItemStatusUpdate":
        if self.status == RoadmapStatus.DONE and self.done_evidence_id is None:
            raise ValueError("done_evidence_id is required when status is DONE")
        return self
```

- [ ] **Step 4: Implement the router**

```python
# radar-api/src/radar_api/routers/roadmap.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select

from radar_api.dependencies import get_db_session
from radar_api.schemas.roadmap import RoadmapItemRead

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


@router.get("/repositories/{repository_id}/roadmap", response_model=list[RoadmapItemRead])
def list_roadmap_items(
    repository_id: int, session: Session = Depends(get_db_session)
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
```

- [ ] **Step 5: Mount the router**

```python
# radar-api/src/radar_api/main.py
from fastapi import FastAPI

from radar_api.routers import findings, repositories, roadmap

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
app.include_router(findings.router)
app.include_router(roadmap.router)
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add radar-api/src/radar_api/schemas/roadmap.py radar-api/src/radar_api/routers/roadmap.py radar-api/src/radar_api/main.py radar-api/tests/test_roadmap.py
git commit -m "feat(radar-api): add GET /repositories/{id}/roadmap"
```

---

### Task 11: Roadmap router — update status

**Files:**
- Modify: `radar-api/src/radar_api/routers/roadmap.py`
- Modify: `radar-api/tests/test_roadmap.py`

**Interfaces:**
- Consumes: `radar_api.auth.require_api_key` (Task 3), `_to_roadmap_item_read` (Task 10)

- [ ] **Step 1: Write the failing tests**

Append to `radar-api/tests/test_roadmap.py`:

```python
from datetime import UTC, datetime

from radar_core.enums import EvidenceType
from radar_core.models.finding import Evidence


def _make_evidence(db_session, finding):
    evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.HUMAN_CONFIRMATION,
        content="fixed in PR #123",
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


def test_update_roadmap_item_status_requires_api_key(client, db_session):
    repo = _make_repository(db_session, "repo-roadmap-noauth")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status", json={"status": "IN_PROGRESS"}
    )

    assert response.status_code == 401


def test_update_roadmap_item_status_returns_404_when_missing(client, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")

    response = client.patch(
        "/roadmap-items/999/status",
        json={"status": "IN_PROGRESS"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 404


def test_update_roadmap_item_status_rejects_no_op_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-noop")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "TODO"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_roadmap_item_status_rejects_done_without_evidence(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-done-no-evidence")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 422


def test_update_roadmap_item_status_rejects_nonexistent_evidence(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-bad-evidence")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE", "done_evidence_id": 999},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 400


def test_update_roadmap_item_status_succeeds_for_non_done_transition(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-in-progress")
    finding = _make_finding_chain(db_session, repo)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.TODO)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_update_roadmap_item_status_succeeds_for_done_with_evidence(client, db_session, monkeypatch):
    monkeypatch.setenv("RADAR_API_KEY", "secret")
    repo = _make_repository(db_session, "repo-roadmap-done")
    finding = _make_finding_chain(db_session, repo)
    evidence = _make_evidence(db_session, finding)
    roadmap_item = _make_roadmap_item(db_session, finding, status=RoadmapStatus.IN_PROGRESS)

    response = client.patch(
        f"/roadmap-items/{roadmap_item.id}/status",
        json={"status": "DONE", "done_evidence_id": evidence.id},
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DONE"
    assert body["done_at"] is not None
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v -k status`
Expected: FAIL (404 on a route that doesn't exist)

- [ ] **Step 3: Add the route**

Add to `radar-api/src/radar_api/routers/roadmap.py` (new imports at the top, new function at the
bottom):

```python
from datetime import UTC, datetime

from radar_core.enums import RoadmapStatus
from radar_core.models.finding import Evidence

from radar_api.auth import require_api_key
from radar_api.schemas.roadmap import RoadmapItemStatusUpdate
```

```python
@router.patch(
    "/roadmap-items/{roadmap_item_id}/status",
    response_model=RoadmapItemRead,
    dependencies=[Depends(require_api_key)],
)
def update_roadmap_item_status(
    roadmap_item_id: int,
    payload: RoadmapItemStatusUpdate,
    session: Session = Depends(get_db_session),
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
        roadmap_item.done_evidence_id = payload.done_evidence_id
        roadmap_item.done_at = datetime.now(UTC)

    roadmap_item.status = payload.status
    session.add(roadmap_item)
    session.commit()
    session.refresh(roadmap_item)
    return _to_roadmap_item_read(roadmap_item)
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd radar-api && uv run pytest tests/test_roadmap.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Commit**

```bash
git add radar-api/src/radar_api/routers/roadmap.py radar-api/tests/test_roadmap.py
git commit -m "feat(radar-api): add PATCH /roadmap-items/{id}/status"
```

---

### Task 12: Docker deployment

**Files:**
- Create: `radar-api/Dockerfile`
- Create: `docker-compose.yml`

**Interfaces:** none (deployment-only task, no Python code)

**Note on the spec:** the spec's `docker-compose.yml` sketch used `build: ./radar-api` for the
`radar-api` service. Because `radar-api` depends on `radar-core` through a `uv` workspace path
reference, the Docker build context must be the repository root (so it can see both
`radar-core/` and `radar-api/`), with the Dockerfile referenced explicitly. Fixed below; same
correction applies to `radar-audit`.

- [ ] **Step 1: Write `radar-api/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-api ./radar-api

RUN uv sync --frozen --package radar-api

EXPOSE 8000

CMD ["uv", "run", "--package", "radar-api", "uvicorn", "radar_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

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

  radar-audit:
    build:
      context: .
      dockerfile: radar-audit/Dockerfile
    environment:
      - RADAR_DATABASE_URL=sqlite:////data/radar.db
    volumes:
      - radar-data:/data
      - ${RADAR_PORTFOLIO_PATH}:/portfolio:ro
    profiles: ["cli"]

  # radar-dashboard:
  #   reserved for item E (Vue 3 + Vite SPA) -- not built yet

volumes:
  radar-data:
```

- [ ] **Step 3: Write `radar-audit/Dockerfile`** (needed for the `docker-compose.yml` reference above; `radar-audit` had no Dockerfile before this increment)

```dockerfile
FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-audit ./radar-audit

RUN uv sync --frozen --package radar-audit

ENTRYPOINT ["uv", "run", "--package", "radar-audit", "radar-audit"]
```

- [ ] **Step 4: Validate the compose file parses**

Run: `docker compose config`
Expected: prints the resolved compose configuration with no errors (requires `RADAR_API_KEY` and
`RADAR_PORTFOLIO_PATH` set in the shell, or pass `RADAR_API_KEY=x RADAR_PORTFOLIO_PATH=/tmp docker
compose config` for a dry validation)

- [ ] **Step 5: Build the `radar-api` image**

Run: `docker compose build radar-api`
Expected: image builds successfully

- [ ] **Step 6: Commit**

```bash
git add radar-api/Dockerfile radar-audit/Dockerfile docker-compose.yml
git commit -m "feat(radar-api): add Docker deployment for radar-api and radar-audit"
```

---

### Task 13: Full workspace verification

**Files:** none created; verification only.

- [ ] **Step 1: Run the full `radar-api` test suite**

Run: `cd radar-api && uv run pytest -v`
Expected: PASS (all tests from Tasks 1-11: 4 + 2 + 3 + 4 + 7 + 11 + 5 + 10 + 13 + 3 + 10 = 72 tests — exact count may drift slightly if a task's step count changed during implementation; the important bar is zero failures)

- [ ] **Step 2: Run `ruff` and `mypy` on `radar-api`**

Run: `cd radar-api && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: PASS, no errors

- [ ] **Step 3: Run the full monorepo test suite to confirm no regression**

Run: `uv run pytest` (from repo root, runs `radar-core`, `radar-audit`, and `radar-api`)
Expected: PASS, same pass count as `radar-audit`/`radar-core` had before this plan plus `radar-api`'s new tests

- [ ] **Step 4: Commit any final formatting fixes if `ruff format` changed files**

```bash
git add -u
git commit -m "chore(radar-api): apply ruff formatting"
```

(Skip this step entirely if Step 2 made no changes — no empty commits.)
