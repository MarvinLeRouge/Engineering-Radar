🇫🇷 Version française | [🇬🇧 English version](developer_guide.md)

---

# Guide développeur

Guide pratique pour travailler sur le code `radar-core` / `radar-audit`.
Pour le workflow de contribution (branches, commits, pull requests), voir
[`CONTRIBUTING.md`](../i18n/fr/CONTRIBUTING.fr.md). Pour la conception globale
du système, voir [`docs/system-design.md`](../system-design.md) et les
docs d'architecture par composant dans
[`docs/architecture/`](../architecture/).

## Prérequis

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (gère le workspace, les dépendances et l'environnement virtuel)
- Une base de données accessible via une chaîne de connexion `RADAR_DATABASE_URL` (SQLite suffit en développement local)

## Structure du workspace

Ce dépôt est un workspace `uv` avec deux packages :

- `radar-core` : le modèle de données partagé (SQLModel) et les migrations Alembic
- `radar-audit` : le moteur d'orchestration d'outils et de normalisation, exposé via la CLI `radar-audit`

```bash
uv sync
```

installe les deux packages et leurs groupes de dépendances dans un seul environnement virtuel de workspace.

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

## Tests

```bash
uv run --package radar-core pytest radar-core/tests --cov=radar_core
uv run --package radar-audit pytest radar-audit/tests --cov=radar_audit
uv run --package radar-api pytest radar-api/tests --cov=radar_api
cd radar-dashboard && npm run test:coverage
```

Certains tests `radar-audit` sont marqués `slow` (vrais téléchargements `npx`/`composer` nécessitant un accès réseau et, pour les runners PHP, une chaîne d'outils PHP/Composer locale). Lancer `pytest -m "not slow"` pour les ignorer localement ; la CI les exécute dans un job séparé, non bloquant (voir ci-dessous).

## Pipeline CI

`.github/workflows/ci.yml` s'exécute à chaque push et pull request vers `main` :

- `radar-core`, `radar-api` et `radar-audit` (rapide, `-m "not slow"`) lancent les tests avec un seuil de couverture de 80% et bloquent la PR en cas d'échec.
- `radar-audit` (lent) lance séparément les tests dépendant de `npx`/`composer` et ne bloque pas la PR.
- `radar-dashboard` lance Vitest avec un seuil de couverture de 80% et bloque la PR en cas d'échec.

## Gates de qualité du code

`ruff` (lint + format) et `mypy --strict` s'exécutent sur `radar-core` et `radar-audit` via des hooks pre-commit (`.pre-commit-config.yaml`) ; la CI ne duplique pas ces vérifications. Installer et lancer les hooks localement avant d'ouvrir une pull request :

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Ajouter un nouveau tool runner

Chaque incrément de normalisation (un par catégorie du Quality Framework, voir [`docs/quality-framework.md`](../quality-framework.md)) suit la même structure :

1. Implémenter un `ToolRunner` dans `radar-audit/src/radar_audit/runners/`, qui invoque l'outil externe et retourne sa sortie brute
2. Ajouter un normalizer qui transforme la sortie brute en score de critère
3. Enregistrer le runner dans `DEFAULT_RUNNERS` dans `radar-audit/src/radar_audit/cli.py`
4. Couvrir les deux par des tests reflétant la structure du code source sous `radar-audit/tests/`
