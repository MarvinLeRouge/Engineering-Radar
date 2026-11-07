🇫🇷 Version française | [🇬🇧 English version](architecture.md)

---

# Architecture - Engineering Radar

> Référence technique publique. Voir [architecture radar-core](architecture/radar-core_architecture.fr.md) et [architecture radar-audit](architecture/radar-audit_architecture.fr.md) pour les détails d'implémentation.

## Vue d'ensemble

Engineering Radar audite un portefeuille de dépôts locaux selon un Quality Framework versionné, en stockant les résultats dans un modèle de données partagé :

- **`radar-core`** - modèle de données SQLModel partagé et historique de migrations Alembic. Aucune logique d'orchestration propre ; tous les autres composants lisent et écrivent dedans.
- **`radar-audit`** - CLI mono-exécution : `radar-audit run` détecte les sous-projets et exécute des outils externes épinglés par stack détectée avec isolation des crashs, `radar-audit score` normalise la sortie brute des outils en lignes `Finding`/`Score` et en éléments de roadmap selon la taxonomie figée, `radar-audit report` produit un rapport Markdown.
- **`radar-api`** - service FastAPI exposant dépôts, rapports, findings, historique des scores et roadmap, avec des routes `PATCH` protégées par `X-API-Key` pour les verdicts humains et les statuts. Documentation OpenAPI sur `/docs`.
- **`radar-dashboard`** - SPA Vue 3 + Vite + Pinia consommant `radar-api` : liste des dépôts, une vue par dépôt avec les onglets Report, Roadmap et Trends, et une page Settings pour la clé d'API.

## Structure du projet

```
engineering-radar/
├── radar-core/src/radar_core/
│   ├── db.py                        # helpers engine/session
│   ├── enums.py, types.py           # enums partagés, type de colonne UTCDateTime
│   ├── observability.py             # configuration des logs structlog + Sentry
│   ├── finding_fingerprint.py       # identité stable d'un finding entre ré-audits
│   ├── finding_ordering.py          # tri des findings par priorité (Python + SQL)
│   ├── improvement_task_grouping.py # clés de regroupement stables des ImprovementTask
│   └── models/                      # Repository, Audit, Finding, Score, Roadmap, ...
├── radar-audit/src/radar_audit/
│   ├── cli.py                       # CLI Typer : run, score, report
│   ├── config.py                    # chargement/validation de portfolio.yaml
│   ├── discovery.py                 # détection de sous-projets par fichier manifeste
│   ├── worktree.py                  # détection des worktrees et chemins ignorés par git
│   ├── scope.py                     # zones hors périmètre par critère (tests, migrations)
│   ├── gitignore.py                 # correspondance avec le .gitignore racine
│   ├── orchestrator.py              # résolution Repository/Audit, exécution de l'AuditPlan
│   ├── runner.py                    # protocole ToolRunner
│   ├── runners/                     # un ToolRunner par outil externe
│   ├── normalizers/                 # raw_output -> Finding/Score, par critère
│   ├── scoring.py                   # score_repository : scores, findings, roadmap
│   ├── roadmap_promotion.py         # findings -> ImprovementTask/RoadmapItem
│   ├── report.py                    # rendu du rapport Markdown
│   └── taxonomy/seed.py             # seed de la taxonomie Quality Framework
├── radar-api/                       # API FastAPI lecture/écriture
├── radar-dashboard/                 # Vue 3 SPA
├── scripts/                         # rebuild.sh, hook changelog, seed de la base e2e
├── docker-compose.yml               # radar-api + radar-dashboard derrière Traefik
└── docs/
    ├── architecture/                # architecture radar-core/radar-audit
    ├── adr/                         # architecture decision records
    └── guides/                      # guide développeur, agrégation des logs
```

## Pour aller plus loin

- [Architecture radar-core](architecture/radar-core_architecture.fr.md)
- [Architecture radar-audit](architecture/radar-audit_architecture.fr.md)
- [Quality Framework](quality-framework.fr.md)
- [Toolchain](toolchain.fr.md)
- [Registre des décisions d'architecture](adr/README.md)
- [Guide développeur](guides/developer_guide.fr.md)
- [Agrégation des logs](guides/log-aggregation.fr.md)
- [README radar-api](../radar-api/README.fr.md)
- [README radar-dashboard](../radar-dashboard/README.fr.md)
- [README radar-online](../radar-online/README.fr.md)
- [Contexte produit](product-context.fr.md)
- [Opérations](operations.fr.md)
