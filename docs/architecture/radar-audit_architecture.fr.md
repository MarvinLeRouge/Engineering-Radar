🇫🇷 Version française | [🇬🇧 English version](radar-audit_architecture.md)

---

# Architecture de radar-audit

`radar-audit` orchestre l'exécution d'outils sur un dépôt et normalise
les résultats bruts dans le modèle de données `radar-core`. Il s'invoque
comme des commandes CLI ponctuelles (`radar-audit run`, `score`, `report`), pas comme un
service tournant en continu, et ne modifie jamais le dépôt audité.

## Pipeline

```text
portfolio.yaml
    ↓
PortfolioConfig (config.py)
    ↓
resolve_repository / get_or_create_audit (orchestrator.py)
    ↓
discover_subprojects (discovery.py)    compute_exclude_paths + compute_ignored_paths (worktree.py)
    ↓                                              ↓
plan_audit → AuditPlan (sous-projets, exclude_paths, ignored_paths)
    ↓
planned_runs (AuditPlan × DEFAULT_RUNNERS, filtré par stack/scope)
    ↓
execute_audit : chaque ToolRunner.run() invoqué avec isolation des crashs, ses
exclude_paths = worktrees + chemins ignorés par git + ses excluded_zones (scope.py)
    ↓
lignes ToolResult (raw_output préservé tel quel)      ← fin de `radar-audit run`
    ↓
score_repository (scoring.py)                         ← `radar-audit score`
    seed de la taxonomie, synchro de Criterion.implemented
    normalizers/*.py : raw_output → Finding / Score, par critère
    report des verdicts humains via Finding.fingerprint
    promotion des findings → ImprovementTask / RoadmapItem (roadmap_promotion.py)
    scores de catégorie, puis score global
    ↓
render_report (report.py) → fichier Markdown          ← `radar-audit report`
```

## Responsabilités

- **`config.py`** : charge et valide `portfolio.yaml` (`repos_root` + liste de dépôts) ; lève `PortfolioConfigError` plutôt que d'échouer silencieusement sur une config malformée.
- **`discovery.py`** : détecte les sous-projets dans un dépôt via fichier manifeste (`pyproject.toml`/`requirements.txt` -> python, `package.json` -> javascript, `composer.json` -> php), sur un niveau de profondeur plus la racine du dépôt elle-même ; retombe sur un unique sous-projet de stack `unknown` si aucun manifeste n'est trouvé.
- **`worktree.py`** : calcule les chemins que chaque runner doit ignorer : les worktrees liés (`compute_exclude_paths`, depuis `git worktree list`), afin que les worktrees imbriqués ne soient jamais comptés deux fois, et les chemins ignorés par git (`compute_ignored_paths`, depuis `git ls-files --others --ignored --exclude-standard --directory`), un dossier entièrement ignoré étant listé une seule fois.
- **`scope.py`** : définit les zones hors périmètre (tests, migrations) et trouve leurs chemins (`out_of_scope_paths`) ; l'orchestrateur les ajoute aux `exclude_paths` de chaque runner dont les `excluded_zones` les mentionnent.
- **`gitignore.py`** : compare des chemins de fichiers au seul `.gitignore` racine du dépôt audité (pas les `.gitignore` imbriqués) ; utilisé par `static_loc_runner`.
- **`orchestrator.py`** : résout les lignes `Repository`/`Audit` (clées sur `commit_sha`, réutilisées lors d'une relance sur un commit inchangé), construit l'`AuditPlan`, filtre les runners par `stack`/`scope`, et exécute chaque run avec une isolation des crashs par outil afin qu'un outil en échec n'interrompe jamais l'audit complet.
- **`runner.py`** : définit le protocole `ToolRunner` (`tool_name`, `tool_version`, `supported_stacks`, `scope`, `timeout_s`, `run()`, plus un `excluded_zones` optionnel) implémenté par chaque intégration d'outil, ainsi que la dataclass `RawToolOutput` retournée par chaque `run()`.
- **`runners/`** : une implémentation `ToolRunner` par outil externe ou vérification du dépôt. La liste enregistrée est `cli.DEFAULT_RUNNERS` (34 runners), par exemple : architecture (dependency-cruiser, pydeps), qualité du code (ruff, ESLint, mypy, PHPStan, radon, jscpd, knip), tests (couverture pytest, Vitest, Pest, présence Playwright), CI (gate pre-commit, workflow CI, actionlint), sécurité (pip-audit, pnpm audit, composer audit, gitleaks, Semgrep, Trivy, hadolint).
- **`normalizers/`** : une fonction par critère, transformant un `ToolResult.raw_output` (ou un ensemble de ceux-ci, ou le dépôt lui-même pour certains critères sans runner) en lignes `Finding`/`Score`. Le registre `CRITERION_NORMALIZERS` de `normalizers/__init__.py` fait foi : un critère est implémenté si et seulement s'il y est enregistré. Les findings marqués faux positifs restent stockés mais sont exclus de tous les scores.
- **`scoring.py`** : `score_repository` score le dernier audit d'un dépôt : seed de la taxonomie, synchro de `Criterion.implemented` depuis le registre, exécution de chaque normalizer, report des verdicts humains via le fingerprint, promotion des findings dans la roadmap, puis écriture des scores de catégorie et du score global.
- **`roadmap_promotion.py`** : regroupe les findings en lignes `ImprovementTask`/`RoadmapItem` par critère et par fichier ; la circularité des dépendances et la duplication de code donnent une tâche par finding.
- **`report.py`** : produit le dernier scoring d'un dépôt au format Markdown et l'écrit sur disque.
- **`taxonomy/seed.py`** : seed de façon idempotente la taxonomie Quality Framework v1.0 (lignes `MethodologyVersion`/`Category`/`Criterion`) depuis une source de vérité YAML, afin que la taxonomie en base corresponde toujours au document de méthodologie gelé.
- **`cli.py`** : le point d'entrée Typer, qui enregistre les `DEFAULT_RUNNERS` et relie le pipeline ci-dessus à une session `radar-core` : `run <repo>|--all [--dry-run] [--config path]` stocke les résultats d'outils, `score <repo>` les score, `report <repo> [--output-dir]` écrit le rapport Markdown (par défaut `radar-audit/reports/<repo>/latest.md`). Le point d'entrée configure les logs et Sentry ; les erreurs attendues affichent un message et sortent avec le code 1, seuls les crashs inattendus remontent à Sentry.

## Décisions de conception clés

- **Isolation des crashs par outil.** Un runner qui plante ou dépasse son timeout produit un `ToolResult` en échec plutôt que d'interrompre l'audit ; tous les autres runners s'exécutent quand même.
- **Le filtrage stack/scope se fait au moment de la planification.** `planned_runs()` croise la stack détectée de chaque sous-projet avec les `supported_stacks` de chaque runner, et son `scope` (`repo` vs `subproject`) avec la structure du sous-projet, afin que les outils spécifiques à un langage ne s'exécutent jamais sur la mauvaise stack.
- **Les worktrees et les chemins ignorés par git sont exclus globalement**, pas par runner : `compute_exclude_paths` et `compute_ignored_paths` s'exécutent une fois par audit et leur résultat est propagé aux `exclude_paths` de chaque runner, plusieurs runners initiaux ayant indépendamment compté deux fois des fichiers de worktrees imbriqués avant cette centralisation.
- **Les tests et migrations sont exclus par critère** : seuls les runners dont les `excluded_zones` les mentionnent les ignorent, si bien qu'un critère comme la couverture de tests voit toujours les tests.
- **Les verdicts humains survivent aux ré-audits.** Un verdict, un statut ou une note posé sur un finding est reporté sur le finding correspondant du scoring suivant via `Finding.fingerprint`.
- **`--dry-run` ne touche jamais la base de données ni n'invoque aucun outil externe** ; il affiche uniquement le plan résolu, ce qui le rend sûr pour déboguer `portfolio.yaml` ou la détection de stack.
- **Ne suppose jamais d'emplacement de base de données.** `RADAR_DATABASE_URL` doit être défini explicitement pour toute invocation autre que dry-run ; voir [`docs/operations.md`](../operations.fr.md#secrets) pour la justification.

## Ajouter un nouvel incrément de normalisation

Voir la section
["Ajouter un nouveau tool runner"](../guides/developer_guide.fr.md#ajouter-un-nouveau-tool-runner)
du guide développeur pour les étapes concrètes.
