🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# radar-audit

Moteur d'orchestration d'outils et de normalisation pour [Engineering-Radar](../README.fr.md).

`radar-audit` détecte les sous-projets d'un dépôt, exécute les outils
d'analyse déterministes pertinents pour chaque stack détectée, et persiste
leurs résultats bruts au regard de la taxonomie versionnée du Quality
Framework. Le scoring transforme ensuite ces résultats en scores, findings,
recommandations et éléments de roadmap. Voir
[`docs/quality-framework.md`](../docs/quality-framework.md) pour la
méthodologie complète et [`docs/toolchain.md`](../docs/toolchain.md) pour la
sélection de chaque outil.

## Couverture

34 runners d'outils (`DEFAULT_RUNNERS` dans `src/radar_audit/cli.py`)
alimentent 30 critères implémentés (`CRITERION_NORMALIZERS` dans
`src/radar_audit/normalizers/__init__.py`) répartis sur les catégories 1, 2,
3, 4, 5, 7, 8 et 9. La catégorie 6 (Performance) est reportée, car son seul
critère a besoin du serveur en fonctionnement du dépôt audité ; les catégories
10 à 15 ne sont pas commencées.

| Catégorie | Outils principaux |
|---|---|
| 1. Architecture & conception | dependency-cruiser, pydeps, Radon (raw), comptage statique de lignes, présence de documentation de conception |
| 2. Qualité du code | Ruff, ESLint, Pint, mypy, tsc, PHPStan, Radon, complexité ESLint, PHPMD, pre-commit gate, jscpd |
| 3. Tests & fiabilité | pytest-cov, Vitest, Pest, heuristique de tests d'intégration, inspection des workflows CI, présence de Playwright |
| 4. Sécurité | pip-audit, pnpm audit, composer audit, gitleaks, Semgrep, Trivy (images), hadolint |
| 5. Maintenabilité | Radon, complexité ESLint, PHPMD, Vulture, Knip, docvet, phpdoc-checker |
| 7. DevOps / CI-CD | actionlint, hadolint ; la parité Traefik et l'automatisation du déploiement lisent le dépôt au moment du scoring |
| 8. Documentation | aucun : le dépôt est lu au moment du scoring |
| 9. Observabilité / exploitation | aucun : le dépôt est lu au moment du scoring |

## Ce qui est exclu

- Pour chaque runner : les worktrees git liés et tous les chemins ignorés par
  git.
- Pour les runners de code applicatif : toujours les migrations, et aussi les
  tests pour la taille des modules, le type-check, la complexité, la
  duplication et les docstrings (le lint et le code mort lisent toujours les
  tests). Défini par runner via `excluded_zones`
  (`src/radar_audit/scope.py`).
- Pour les runners limités à un sous-projet : les autres sous-projets
  imbriqués dedans.

## Prérequis

`radar-audit` écrit dans la même base SQLite que les migrations Alembic de
`radar-core`. Avant de lancer un premier audit réel (hors `--dry-run`),
appliquez les migrations sur la base cible :

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

## Usage

À lancer depuis la racine du dépôt, avec `RADAR_DATABASE_URL` définie (ou
`.env` sourcé). L'exécution locale est la voie prise en charge : l'image du
profil Docker `cli` est une image Python simple, sans les outils d'analyse
(Composer, npx, Docker), et ne peut donc pas mener un audit complet.

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-audit radar-audit run <repo-name>
    uv run --package radar-audit radar-audit run --all
    uv run --package radar-audit radar-audit run <repo-name> --dry-run
    uv run --package radar-audit radar-audit score <repo-name>
    uv run --package radar-audit radar-audit report <repo-name>

- `run` enregistre uniquement les résultats bruts des outils. `--all` audite
  tous les dépôts de `portfolio.yaml`, `--config` pointe vers un autre
  fichier de portfolio. `--dry-run` affiche les worktrees exclus, le nombre
  de chemins ignorés par git, les sous-projets et les runners prévus, sans
  toucher à la base de données.
- `score` normalise le dernier audit en scores, findings, recommandations et
  éléments de roadmap.
- `report` écrit un rapport Markdown du dernier score, par défaut dans
  `radar-audit/reports/<repo-name>/latest.md` (ignoré par git, `--output-dir`
  pour le changer).

Le périmètre des dépôts et la racine locale de checkout
(`repos_root: ~/projets`) sont configurés dans `portfolio.yaml` (versionné
dans ce répertoire).
