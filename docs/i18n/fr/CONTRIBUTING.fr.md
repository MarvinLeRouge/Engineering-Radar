🇫🇷 Version française | [🇬🇧 English version](../../../CONTRIBUTING.md)

---

# Contribuer à Engineering Radar

Il s'agit principalement d'un projet personnel. Les contributions externes (signalements de bugs, corrections, petites améliorations) sont bienvenues mais dans un périmètre limité.

## Prérequis

- Python 3.14 (épinglé dans `.python-version`, uv l'installe s'il manque)
- [`uv`](https://docs.astral.sh/uv/) pour la gestion des dépendances
- Node.js `^22.18.0 || ^23.0.0 || >=24.12.0` (le champ `engines` de `radar-dashboard/package.json` ; la CI utilise la 24) et npm, pour le dashboard

## Installation locale

```bash
git clone https://github.com/MarvinLeRouge/Engineering-Radar.git
cd Engineering-Radar
uv sync
npm ci --prefix radar-dashboard
uv run pre-commit install
```

## Lancer les tests

```bash
uv run --package radar-core pytest
uv run --package radar-audit pytest
uv run --package radar-api pytest
cd radar-dashboard
npm run test:coverage   # tests unitaires Vitest avec couverture
npm run test:e2e        # tests end-to-end Playwright (lancer `npx playwright install chromium` une fois avant)
```

## Workflow

1. Forker le dépôt et créer une branche à partir de `main`.
2. Faire la modification, avec des tests qui la couvrent.
3. Commiter en suivant la convention ci-dessous.
4. Pousser et ouvrir une pull request vers `main`.
5. Les hooks pre-commit (voir ci-dessous) doivent passer avant la revue.

## Nommage des branches

| Type | Préfixe |
|---|---|
| Fonctionnalité | `feat/description-courte` |
| Correction | `fix/description-courte` |
| Maintenance | `chore/description-courte` |
| Documentation | `docs/description-courte` |
| Refactoring | `refactor/description-courte` |
| Tests | `test/description-courte` |

Minuscules, kebab-case, sans caractères spéciaux.

## Convention de commit

Suivre [Conventional Commits](https://www.conventionalcommits.org/), impératif, minuscules, sans point final, avec une section `Modified files:` obligatoire :

```
<type>(<scope optionnel>): <résumé court>

Modified files:
- chemin/vers/fichier-a.ext - ce qui a été modifié
- chemin/vers/fichier-b.ext - ce qui a été modifié
```

Types : `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`.

## Style de code

Les hooks pre-commit (`.pre-commit-config.yaml`) vérifient chaque commit :

- Python (`radar-core`, `radar-audit`, `radar-api`) : `ruff` (lint, avec corrections), `ruff-format` et `mypy --strict` par package.
- Dashboard (`radar-dashboard`) : `oxlint` et `eslint` (avec corrections), `prettier` et `vue-tsc`, via ses scripts npm. Ils nécessitent d'avoir lancé `npm ci` dans `radar-dashboard/`.

Un hook qui corrige ou reformate des fichiers fait échouer le commit : relire les modifications et commiter à nouveau. Lancer `uv run pre-commit run --all-files` pour tout vérifier d'un coup.

La CI (`.github/workflows/ci.yml`) lance les tests de chaque package avec un seuil de couverture de 80 %, les vérifications de lint, de format et de types du dashboard, ses tests end-to-end Playwright, et un scan `pip-audit` des dépendances Python verrouillées (`uv.lock`) qui échoue sur toute vulnérabilité connue. Le lint et la vérification de types Python ne tournent que dans les hooks pre-commit.

## Code de conduite

Ce projet suit un [Code de conduite](CODE_OF_CONDUCT.fr.md). En participant, vous vous engagez à le respecter.

## Licence

En contribuant, vous acceptez que vos contributions soient distribuées sous la licence du projet (voir [LICENSE](../../../LICENSE)).
