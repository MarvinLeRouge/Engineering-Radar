🇫🇷 Version française | [🇬🇧 English version](developer_guide.md)

---

# Guide développeur

Guide pratique pour travailler sur le code de `radar-core`, `radar-audit`,
`radar-api` et `radar-dashboard`.
Pour le workflow de contribution (branches, commits, pull requests), voir
[`CONTRIBUTING.md`](../i18n/fr/CONTRIBUTING.fr.md). Pour la conception globale
du système, voir [`docs/system-design.md`](../system-design.md) et les
docs d'architecture par composant dans
[`docs/architecture/`](../architecture/).

## Prérequis

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (gère le workspace, les dépendances et l'environnement virtuel)
- Une base de données accessible via une chaîne de connexion `RADAR_DATABASE_URL` (SQLite suffit en développement local)
- Pour le dashboard : Node.js `^22.18.0 || ^23.0.0 || >=24.12.0` (le champ `engines` de `radar-dashboard/package.json` ; la CI utilise la 24) et npm, puis `npm ci` dans `radar-dashboard/` (les hooks pre-commit du dashboard en ont aussi besoin)

## Structure du workspace

Ce dépôt est un workspace `uv` avec trois packages Python :

- `radar-core` : le modèle de données partagé (SQLModel) et les migrations Alembic
- `radar-audit` : le moteur d'orchestration d'outils et de normalisation, exposé via la CLI `radar-audit`
- `radar-api` : le service FastAPI que lit le dashboard (voir [`radar-api/README.fr.md`](../../radar-api/README.fr.md))

```bash
uv sync
```

installe les trois packages et leurs groupes de dépendances dans un seul environnement virtuel de workspace.

`radar-dashboard` (Vue 3 + Vite + Pinia) est à côté, en projet npm distinct, hors du workspace `uv`.

## Base de données et migrations

Définir `RADAR_DATABASE_URL` avant toute opération touchant la base de données, par exemple :

```bash
export RADAR_DATABASE_URL="sqlite:///./radar.db"
```

Appliquer les migrations :

```bash
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
```

Créer une nouvelle migration après avoir modifié un modèle dans `radar-core/src/radar_core/models/` :

```bash
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "describe the change"
```

Toujours relire les migrations autogénérées avant de les committer.

## Lancer le moteur d'audit

`radar-audit` lit un fichier `portfolio.yaml` listant les dépôts à auditer :

```yaml
repos_root: ~/projets
repositories:
  - name: some-repo
  - name: another-repo
```

Prévisualiser le plan d'un dépôt sans exécuter aucun outil :

```bash
uv run radar-audit run some-repo --dry-run
```

Lancer un audit réel (écrit les résultats en base, nécessite `RADAR_DATABASE_URL`) :

```bash
uv run radar-audit run some-repo
# ou, pour tous les dépôts listés dans portfolio.yaml :
uv run radar-audit run --all
```

Par défaut, la CLI lit `radar-audit/portfolio.yaml` ; passer `--config` pour pointer ailleurs.

`run` ne fait que stocker les résultats bruts des outils. La notation est une étape à part :

```bash
# normaliser le dernier audit en notes, constats, recommandations et éléments de roadmap :
uv run radar-audit score some-repo
# produire le rapport Markdown du dernier scoring, dans radar-audit/reports/some-repo/latest.md
# (ignoré par git) par défaut, ou sous --output-dir :
uv run radar-audit report some-repo
```

Un audit lance la suite de tests propre à chaque dépôt avec ses dépendances installées (depuis `uv.lock` pour un projet uv, dans un environnement temporaire qui laisse le dépôt intact ; sinon depuis les `requirements*.txt`). Prévoir la durée réelle de la suite : pytest peut tourner jusqu'à 15 minutes par sous-projet (la suite radar-audit d'Engineering-Radar prend environ 10 minutes).

## Tests

```bash
uv run --package radar-core pytest radar-core/tests --cov=radar_core
uv run --package radar-audit pytest radar-audit/tests --cov=radar_audit
uv run --package radar-api pytest radar-api/tests --cov=radar_api
cd radar-dashboard && npm run test:coverage
```

Certains tests `radar-audit` sont marqués `slow` (vrais téléchargements `npx`/`composer` nécessitant un accès réseau et, pour les runners PHP, une chaîne d'outils PHP/Composer locale). Lancer `pytest -m "not slow"` pour les ignorer localement ; la CI les exécute dans un job séparé, non bloquant (voir ci-dessous).

Les tests end-to-end (Playwright) pilotent le dashboard compilé contre un vrai `radar-api`, sur une base SQLite jetable remplie par `scripts/seed_e2e_db.py`, avec leur propre clé d'API de test et leurs propres ports (8020, 4180) : ils ne touchent jamais `radar.db`, le `.env` ni les services en cours. Télécharger le navigateur une fois, puis les lancer :

```bash
cd radar-dashboard
npx playwright install chromium
npm run test:e2e
```

## Pipeline CI

`.github/workflows/ci.yml` s'exécute à chaque push et pull request vers `main` :

- `radar-core`, `radar-api` et `radar-audit` (rapide, `-m "not slow"`) lancent les tests avec un seuil de couverture de 80% et bloquent la PR en cas d'échec.
- `radar-audit` (lent) lance séparément les tests dépendant de `npx`/`composer` et ne bloque pas la PR.
- `radar-dashboard` lance Vitest avec un seuil de couverture de 80% et bloque la PR en cas d'échec.
- `radar-dashboard` (e2e) lance la suite Playwright et bloque la PR en cas d'échec ; le rapport HTML est conservé comme artefact en cas d'échec.

## Gates de qualité du code

Les hooks pre-commit (`.pre-commit-config.yaml`) s'exécutent à chaque commit :

- `ruff` (avec `--fix`) et `ruff-format` sur `radar-core`, `radar-audit` et `radar-api`
- `mypy` (mode strict, défini dans le `pyproject.toml` racine), un hook par package Python
- dashboard : `eslint` + `oxlint` (`npm run lint`), `prettier` (`npm run format`) et `vue-tsc` (`npm run type-check`)
- `changelog`, un hook `post-commit` qui régénère `CHANGELOG.md` avec git-cliff

La CI refait le lint, la vérification de format (`prettier --check`) et `vue-tsc` du dashboard, mais pas `ruff` ni `mypy` : le lint et la vérification de types Python ne tournent que dans pre-commit. Installer et lancer les hooks localement avant d'ouvrir une pull request :

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Ajouter un nouveau tool runner

Chaque incrément de normalisation (un par catégorie du Quality Framework, voir [`docs/quality-framework.fr.md`](../quality-framework.fr.md)) suit la même structure :

1. Implémenter un `ToolRunner` dans `radar-audit/src/radar_audit/runners/`, qui invoque l'outil externe et retourne sa sortie brute. Si le critère ne juge que le code applicatif, définir `excluded_zones` (voir `radar-audit/src/radar_audit/scope.py`) pour que l'outil n'analyse jamais les tests ni les migrations
2. Ajouter un normalizer dans `radar-audit/src/radar_audit/normalizers/` qui transforme la sortie brute en score de critère
3. Enregistrer le normalizer dans `CRITERION_NORMALIZERS` (`radar-audit/src/radar_audit/normalizers/__init__.py`), avec pour clé la catégorie et le nom du critère : c'est ce qui marque le critère comme implémenté (`Criterion.implemented` passe à vrai au `score` suivant)
4. Enregistrer le runner dans `DEFAULT_RUNNERS` dans `radar-audit/src/radar_audit/cli.py`
5. Couvrir les deux par des tests reflétant la structure du code source sous `radar-audit/tests/`

## Travailler sur le dashboard

Pour les scripts, la structure et le serveur de développement local du dashboard, voir [`radar-dashboard/README.fr.md`](../../radar-dashboard/README.fr.md).
