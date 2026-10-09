🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# radar-api

Service FastAPI minimal pour [Engineering-Radar](../README.fr.md).

`radar-api` expose des points d'accès en lecture sur le modèle de données de
Engineering-Radar (dépôts, audits, scores, findings, roadmap) ainsi
que des points d'accès en écriture restreints, confirmés uniquement par un
humain.

## Variables d'environnement requises

- `RADAR_DATABASE_URL` — la même base SQLite que celle utilisée par `radar-core`/`radar-audit`.
- `RADAR_API_KEY` — requise pour tous les points d'accès en écriture (`PATCH`) ; les requêtes sans en-tête `X-API-Key` valide correspondant à cette valeur reçoivent un `401`.

## Points d'accès

### Points d'accès en lecture

- `GET /repositories` — liste tous les dépôts avec leur statut d'audit et leur score global les plus récents.
- `GET /repositories/{repository_id}` — détail d'un dépôt.
- `GET /repositories/{repository_id}/report` — rapport de qualité complet (catégories, critères, findings, recommandations) pour le dernier run de scoring.
- `GET /repositories/{repository_id}/badge` — payload de badge compatible shields.io pour le dernier score global.
- `GET /repositories/{repository_id}/findings` — findings du dernier run de scoring, filtrables via les paramètres de requête `status` et `severity`.
- `GET /repositories/{repository_id}/roadmap` — éléments de roadmap liés aux findings du dépôt.

### Points d'accès en écriture (requièrent `X-API-Key`)

- `PATCH /findings/{finding_id}/verdict` — met à jour le verdict humain d'un finding.
- `PATCH /findings/{finding_id}/status` — met à jour le statut d'un finding.
- `PATCH /roadmap-items/{roadmap_item_id}/status` — met à jour le statut d'un élément de roadmap ; la transition vers `DONE` requiert un `done_evidence_id` référençant une ligne `Evidence` liée à l'un des findings de l'élément de roadmap.

## Lancement en local

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    export RADAR_API_KEY="votre-cle-secrete"
    uv run --package radar-api uvicorn radar_api.main:app --reload

## Migrations de base de données

`radar-api` n'exécute pas les migrations elle-même, elle s'attend à ce que la
base soit déjà migrée via la configuration Alembic de `radar-core` :

    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

Sur un volume Docker neuf, rien n'exécute les migrations automatiquement,
cette étape doit être lancée manuellement (par exemple en surchargeant le
point d'entrée du conteneur `radar-audit`, ou en exécutant la commande en
local sur le même fichier de base de données) avant que les points d'accès de
l'API ne fonctionnent. Sans cela, chaque point d'accès renvoie un `500`.

## Docker

    docker compose build radar-api
    docker compose up radar-api

`RADAR_API_KEY` doit être définie dans l'environnement du shell avant
`docker compose up` (référencée via `${RADAR_API_KEY}` dans
`docker-compose.yml`). `RADAR_PORTFOLIO_PATH` ne concerne que le profil CLI
séparé `radar-audit`.

`radar-api` est raccordée à l'instance Traefik partagée (même convention que
les autres projets `marvinlerouge`) : réseau externe `traefik-public`,
`Host(\`radar-api.marvinlerouge.local\`)` sur l'entrypoint `web` en local. Le
routeur de production (`radar-api.marvinlerouge.dev`, `websecure`/
`letsencrypt`) n'est pas encore raccordé, ce dépôt n'a pas de compose de
production pour l'instant.

## Badge de qualité

Tout dépôt audité par Engineering-Radar peut lier un badge
shields.io de type [endpoint](https://shields.io/badges/endpoint-badge) dans
son README, alimenté par `GET /repositories/{repository_id}/badge`. Rien
d'autre (aucun contenu de rapport, aucun score) n'est jamais écrit dans le
dépôt audité, seule cette ligne Markdown :

    [![Quality](https://img.shields.io/endpoint?url=https%3A%2F%2Fradar-api.marvinlerouge.dev%2Frepositories%2F{repository_id}%2Fbadge)](https://radar-api.marvinlerouge.dev/repositories/{repository_id}/report)

Remplacer `{repository_id}` par l'identifiant numérique du dépôt dans la base
de Radar. En local, remplacer le domaine par `radar-api.marvinlerouge.local`.

Le lien pointe pour l'instant vers le point d'accès JSON brut `/report`
(aucune page de rapport lisible par un humain n'existe encore, ce sera
l'item E, la SPA `radar-dashboard`). Une fois le dashboard livré, le lien
devra pointer vers la page de rapport du dashboard plutôt que vers le JSON
brut.

## Lancer les tests

    uv run --package radar-api pytest

## Limitations connues

- L'utilisation de `httpx` avec `starlette.testclient` émet actuellement un `DeprecationWarning` dans les tests (uniquement en test, aucun effet à l'exécution) ; aucune action nécessaire sauf changement de la pile de dépendances.
- Le service ne valide pas `RADAR_DATABASE_URL` / `RADAR_API_KEY` au démarrage, une valeur manquante ou mal configurée se traduit par un `500` (URL de base de données) ou un `401` sur chaque écriture (clé API) plutôt qu'un échec au démarrage. Suivi comme amélioration future.
- Le mode WAL de SQLite n'est pas encore activé, les lectures concurrentes de l'API et les écritures de `radar-audit` sur le même fichier de base de données peuvent occasionnellement provoquer une erreur "database is locked". Suivi comme amélioration future (concerne `radar-core`).
