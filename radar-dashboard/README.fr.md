🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# radar-dashboard

Dashboard web pour [Engineering-Radar](../README.fr.md).

`radar-dashboard` est une application monopage au-dessus de
[`radar-api`](../radar-api/README.fr.md) : elle affiche le rapport, la roadmap
et l'évolution des scores de chaque dépôt audité, et permet à un humain
d'enregistrer verdicts, statuts et notes sur les findings et les éléments de
roadmap.

## Pages

- `/` : liste des dépôts.
- `/repositories/<slug>-<id>` : détail d'un dépôt, en trois onglets.
  - Report : barre de risque pondéré, résumé par sévérité, catégories et
    critères avec jauges de score, marqueurs "Not implemented yet" (critères
    prévus repliés), findings groupés par sévérité puis par fichier, bouton
    "More" qui charge 1000 findings à la fois, section des findings écartés,
    listes de verdict et de statut, et note de verdict avec raisons
    prédéfinies.
  - Roadmap : éléments de roadmap, leur statut, la preuve de réalisation, et
    un export Markdown.
  - Trends : graphiques d'historique des scores et du risque pondéré, les
    catégories non implémentées étant grisées.
- `/settings` : clé API.

## Stack

Vue 3, Vite, Pinia, Vue Router, Chart.js (`vue-chartjs`), Sentry (`@sentry/vue`).
Tests avec Vitest et Playwright. Node `^22.18 || ^23 || >=24.12` (la CI
utilise la 24).

## Développement

    cd radar-dashboard
    npm ci
    npm run dev

Le serveur de développement Vite redirige `/api` vers `radar-api` (préfixe
retiré), par défaut sur `http://localhost:8000`. Pour viser une autre API,
utiliser `RADAR_API_URL` :

    RADAR_API_URL=http://localhost:8020 npm run dev

## Clé API

La lecture ne demande aucune clé. Les appels `PATCH` (verdict, statut, note,
statut de roadmap) envoient la clé enregistrée sur la page Settings dans
l'en-tête `X-API-Key` ; elle doit correspondre à la `RADAR_API_KEY` de
`radar-api`. La clé est conservée uniquement dans le stockage de session du
navigateur.

## Tests

    npm run test:unit       # Vitest, mode watch
    npm run test:coverage   # Vitest, exécution unique avec couverture
    npm run test:e2e        # Playwright

L'exécution de bout en bout gère toute sa pile (`playwright.config.ts`) : elle
alimente une base SQLite jetable (`scripts/seed_e2e_db.py`), démarre sa propre
instance de `radar-api` sur le port 8020 via `uv`, et sert un build de
production sur le port 4180. Elle ne touche jamais au vrai `radar.db`, au
`.env` ni aux services en cours. Elle nécessite `uv` et un navigateur
Playwright (`npx playwright install chromium`).

## Contrôles qualité

    npm run lint        # oxlint puis ESLint, avec --fix
    npm run format      # Prettier sur src/
    npm run type-check  # vue-tsc

Le hook pre-commit lance ces trois commandes sur les changements du
dashboard. La CI exécute le lint, une vérification Prettier, le type-check,
les tests avec couverture et les tests de bout en bout.

## Docker

    scripts/rebuild.sh radar-dashboard

À lancer depuis la racine du repo. L'image construit l'application avec Node,
puis la sert avec nginx (repli SPA sur `index.html`). Traefik l'expose sur
`radar.marvinlerouge.local`, qui route aussi `/api` vers `radar-api`. Sentry
est optionnel : les build args `VITE_SENTRY_DSN` (issu de
`SENTRY_FRONTEND_DSN`) et `VITE_SENTRY_ENVIRONMENT` sont intégrés au moment du
build, les changer demande donc une reconstruction. Voir
[`docs/operations.fr.md`](../docs/operations.fr.md).
