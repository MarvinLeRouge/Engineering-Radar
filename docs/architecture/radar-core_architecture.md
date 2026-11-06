[🇫🇷 Version française](radar-core_architecture.fr.md) | 🇬🇧 English version

---

# radar-core architecture

`radar-core` is the shared data model and migration layer used by every
other component of the system. It has no orchestration logic of its own:
it defines the SQLModel entities, the database session helpers, and the
Alembic migration history that `radar-audit` and `radar-api` read and
write against.

## Responsibilities

- Define the audit data model as SQLModel classes (one table per class)
- Own the Alembic migration history (`radar-core/alembic/`)
- Provide `get_engine` / `get_session` helpers (`radar_core.db`), including SQLite foreign-key enforcement since SQLite disables it by default
- Provide shared enums and the `UTCDateTime` column type (`radar_core.enums`, `radar_core.types`) used to guarantee timezone-aware timestamps across every table
- Provide the helpers both writers and readers need: finding fingerprints, finding priority ordering, improvement task group keys, and logging/Sentry setup

`radar-core` never talks to external tools or the filesystem of an
audited repository; that boundary belongs entirely to `radar-audit`.

## Entity map

```text
Repository
    └─ Audit (one per repo, per commit_sha)
           └─ ToolResult (one per tool run per subproject)

MethodologyVersion
    └─ Category
           └─ Criterion

ScoringRun (references an Audit + a MethodologyVersion)
    └─ Score (per Criterion or per Category)

Finding (references a ScoringRun, a Criterion, optionally a ToolResult)
    └─ Evidence (references the Finding, optionally a Score)
    └─ Recommendation (references the Finding)

ImprovementTask
    └─ RoadmapItem (one-to-one, tracks status/done evidence)
    └─ linked to Finding via FindingImprovementTaskLink (many-to-many)

Snapshot (point-in-time rollup, independent table, not written by any component yet)
```

## Module layout

```text
radar-core/src/radar_core/
    db.py            engine/session helpers, SQLite FK pragma
    enums.py         shared enum types
    types.py         UTCDateTime column type
    observability.py configure_logging (structlog), init_error_tracking (Sentry)
    finding_fingerprint.py       compute_fingerprint: stable finding identity
    finding_ordering.py          sort_findings_by_priority and its SQL twin PRIORITY_ORDER_BY
    improvement_task_grouping.py compute_task_group_key
    models/
        repository.py    Repository
        audit.py         Audit, ToolResult
        methodology.py   MethodologyVersion, Category, Criterion
        scoring.py       ScoringRun, Score
        finding.py       Finding, Evidence, Recommendation
        roadmap.py       ImprovementTask, RoadmapItem
        snapshot.py      Snapshot
        links.py         FindingImprovementTaskLink
```

## Key design decisions

- **Raw tool output is preserved.** `ToolResult.raw_output` stores the
  tool's full JSON output as-is; normalization into `Finding`/`Score`
  happens downstream in `radar-audit`, so a finding can always be traced
  back to the exact evidence that produced it.
- **Audits are keyed on `(repository_id, commit_sha)`.** Re-running an
  audit against an unchanged commit reuses the same `Audit` row rather
  than creating a duplicate.
- **Methodology is versioned explicitly.** Every `ScoringRun` references
  the `MethodologyVersion` it was scored against, so criteria weights or
  definitions can change over time without invalidating historical
  scores.
- **`Criterion.implemented` says what radar-audit can score.** It is
  synced on every `radar-audit score` from the normalizer registry, so
  readers can tell "not implemented" apart from "scored 0".
- **Findings have a stable identity.** `Finding.fingerprint` identifies
  the same underlying finding across re-audits and carries its human
  verdict, status and `verdict_note` (200 characters max) forward.
  `Finding.magnitude` is an optional numeric size (for example a
  cyclomatic complexity) used in priority ordering.
- **Improvement tasks are upserted, not recreated.** Each
  `ImprovementTask` belongs to one criterion and has a unique
  `group_key` (a hash of criterion and file, or the finding fingerprint
  for one-task-per-finding criteria), so a human-set `RoadmapItem`
  survives a re-audit.
- **Timestamps are always timezone-aware.** The `UTCDateTime` type is
  used on every datetime column and is covered by a dedicated test
  asserting UTC round-trip behavior, to avoid silent naive-datetime bugs.

## Migrations

Alembic is configured with an explicit-URL `env.py` (`radar-core/alembic/env.py`): it requires `RADAR_DATABASE_URL` and never assumes a default connection string, matching the same rule enforced in the `radar-audit` CLI. See the [developer guide](../guides/developer_guide.md#database-and-migrations) for the exact commands.
