[🇫🇷 Version française](architecture.fr.md) | 🇬🇧 English version

---

# Architecture - Engineering Radar

> Public technical reference. See [radar-core architecture](architecture/radar-core_architecture.md) and [radar-audit architecture](architecture/radar-audit_architecture.md) for implementation details.

## Overview

Engineering Radar audits a portfolio of local repositories against a versioned Quality Framework, storing results in a shared data model:

- **`radar-core`** - shared SQLModel data model and Alembic migration history. No orchestration logic of its own; every other component reads and writes against it.
- **`radar-audit`** - one-shot CLI: `radar-audit run` discovers sub-projects and runs pinned external tools per detected stack with crash isolation, `radar-audit score` normalizes raw tool output into `Finding`/`Score` rows and roadmap items against the frozen taxonomy, `radar-audit report` renders a Markdown report.
- **`radar-api`** - FastAPI service exposing repositories, reports, findings, score history and roadmap, plus `X-API-Key` protected `PATCH` routes for human verdicts and statuses. OpenAPI docs at `/docs`.
- **`radar-dashboard`** - Vue 3 + Vite + Pinia SPA consuming `radar-api`: a repository list, a per-repository view with Report, Roadmap and Trends tabs, and a Settings page for the API key.

## Project structure

```
engineering-radar/
├── radar-core/src/radar_core/
│   ├── db.py                        # engine/session helpers
│   ├── enums.py, types.py           # shared enums, UTCDateTime column type
│   ├── observability.py             # structlog logging + Sentry setup
│   ├── finding_fingerprint.py       # stable finding identity across re-audits
│   ├── finding_ordering.py          # finding priority ordering (Python + SQL)
│   ├── improvement_task_grouping.py # stable ImprovementTask group keys
│   └── models/                      # Repository, Audit, Finding, Score, Roadmap, ...
├── radar-audit/src/radar_audit/
│   ├── cli.py                       # Typer CLI: run, score, report
│   ├── config.py                    # portfolio.yaml loading/validation
│   ├── discovery.py                 # sub-project detection per manifest file
│   ├── worktree.py                  # worktree and git-ignored path discovery
│   ├── scope.py                     # per-criterion out-of-scope zones (tests, migrations)
│   ├── gitignore.py                 # root .gitignore matching
│   ├── orchestrator.py              # Repository/Audit resolution, AuditPlan execution
│   ├── runner.py                    # ToolRunner protocol
│   ├── runners/                     # one ToolRunner per external tool
│   ├── normalizers/                 # raw_output -> Finding/Score, per criterion
│   ├── scoring.py                   # score_repository: scores, findings, roadmap
│   ├── roadmap_promotion.py         # findings -> ImprovementTask/RoadmapItem
│   ├── report.py                    # Markdown report rendering
│   └── taxonomy/seed.py             # Quality Framework taxonomy seeding
├── radar-api/                       # FastAPI read/write API
├── radar-dashboard/                 # Vue 3 SPA
├── scripts/                         # rebuild.sh, changelog hook, e2e DB seed
├── docker-compose.yml               # radar-api + radar-dashboard behind Traefik
└── docs/
    ├── architecture/                # radar-core/radar-audit architecture
    ├── adr/                         # architecture decision records
    └── guides/                      # developer guide, log aggregation
```

## Further reading

- [radar-core architecture](architecture/radar-core_architecture.md)
- [radar-audit architecture](architecture/radar-audit_architecture.md)
- [Quality Framework](quality-framework.md)
- [Toolchain](toolchain.md)
- [Architecture decision records](adr/README.md)
- [Developer guide](guides/developer_guide.md)
- [Log aggregation](guides/log-aggregation.md)
- [radar-api README](../radar-api/README.md)
- [radar-dashboard README](../radar-dashboard/README.md)
- [radar-online README](../radar-online/README.md)
- [Product context](product-context.md)
- [Operations](operations.md)
