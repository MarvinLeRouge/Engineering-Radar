🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# radar-api

Service FastAPI minimal pour [Engineering-Radar](../README.fr.md).

`radar-api` expose des points d'accès en lecture sur le modèle de données de
Engineering-Radar (dépôts, audits, scores, findings, roadmap) ainsi
que des points d'accès en écriture restreints, confirmés uniquement par un
humain.

## Variables d'environnement requises

- `RADAR_DATABASE_URL` : la même base SQLite que celle utilisée par `radar-core`/`radar-audit`.
- `RADAR_API_KEY` : requise pour tous les points d'accès en écriture (`PATCH`) ; les requêtes sans en-tête `X-API-Key` valide correspondant à cette valeur reçoivent un `401`.

## Variables d'environnement optionnelles

- `SENTRY_DSN`, `SENTRY_ENVIRONMENT` : suivi d'erreurs Sentry, désactivé quand
  le DSN est vide (dans Docker, `SENTRY_DSN` provient de `SENTRY_BACKEND_DSN`).
- `RADAR_LOG_LEVEL` (`info` par défaut), `RADAR_LOG_FORMAT` (`json` ou
  `console` ; vide signifie JSON sauf si stderr est un terminal).

Chaque requête écrit une ligne de log structurée `request_handled` (méthode,
chemin, statut, durée ; jamais la query string, les en-têtes ni le corps).
Voir [`docs/operations.fr.md`](../docs/operations.fr.md).

## Points d'accès

La documentation OpenAPI interactive est servie sur `/docs`. Il n'y a pas de
point d'accès de health check.

### Points d'accès en lecture

- `GET /repositories` : liste tous les dépôts avec leur statut d'audit et leur score global les plus récents.
- `GET /repositories/{repository_id}` : détail d'un dépôt.
- `GET /repositories/{repository_id}/report` : rapport de qualité complet (catégories, critères, findings, recommandations) pour le dernier run de scoring (ou `?scoring_run_id=`), avec son `scoring_run_id`, le `risk` pondéré par sévérité et sa somme `risk_index`. Chaque critère liste ses 1000 premiers findings par ordre de priorité, avec `findings_total`, `severity_counts` et `dismissed_count` qui les comptent tous. Critères et catégories portent `implemented` ; ceux qui ne sont pas implémentés sont listés en dernier.
- `GET /repositories/{repository_id}/report/criteria/{criterion_id}/findings?scoring_run_id=&offset=` : les pages suivantes des findings d'un critère, 1000 à la fois, dans le même ordre (dernier run de scoring si `scoring_run_id` est omis).
- `GET /repositories/{repository_id}/score-history` : un point par run de scoring, du plus ancien au plus récent, avec le score global, les scores par catégorie (chacun avec `implemented`), `risk` et `risk_index`.
- `GET /repositories/{repository_id}/badge` : payload de badge compatible shields.io pour le dernier score global.
- `GET /repositories/{repository_id}/findings` : findings du dernier run de scoring, filtrables via les paramètres de requête `status` et `severity`.
- `GET /repositories/{repository_id}/roadmap` : éléments de roadmap liés aux findings du dépôt, triés par catégorie, critère, priorité (la plus haute d'abord) et titre.
- `GET /roadmap-items/{roadmap_item_id}/evidence-candidates` : lignes `Evidence` des findings liés à un élément de roadmap, utilisables comme `done_evidence_id`.

### Points d'accès en écriture (requièrent `X-API-Key`)

- `PATCH /findings/{finding_id}/verdict` : met à jour le verdict humain d'un finding.
- `PATCH /findings/{finding_id}/status` : met à jour le statut d'un finding.
- `PATCH /findings/{finding_id}/note` : définit la courte note qui explique le verdict d'un finding (200 caractères au plus, espaces de bord retirés ; un texte vide l'efface).
- `PATCH /roadmap-items/{roadmap_item_id}/status` : met à jour le statut d'un élément de roadmap ; la transition vers `DONE` requiert un `done_evidence_id` référençant une ligne `Evidence` liée à l'un des findings de l'élément de roadmap.

## Lancement en local

Copie `.env.example` (racine du repo) vers `.env`, renseigne un vrai
`RADAR_API_KEY`, puis charge-le dans le shell avant de lancer le serveur
(depuis la racine du repo, pas depuis `radar-api/`) :

    set -a && source .env && set +a
    uv run --package radar-api uvicorn radar_api.main:app --reload

Ni `radar-api` ni `radar-audit` ne chargent `.env` automatiquement (voir la
politique "never assumes a default" de `config.py`) : il faut le sourcer dans
chaque nouveau shell. Sans fichier `.env`, exporter directement les deux
variables fonctionne aussi :

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    export RADAR_API_KEY="votre-cle-secrete"
    uv run --package radar-api uvicorn radar_api.main:app --reload

## Migrations de base de données

`radar-api` n'exécute pas les migrations elle-même, elle s'attend à ce que la
base soit déjà migrée via la configuration Alembic de `radar-core` :

    set -a && source .env && set +a
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

Rien n'exécute les migrations automatiquement, et sans elles chaque point
d'accès renvoie un `500`. Le volume Docker `radar-data` est lié au dossier du
projet sur l'hôte (`RADAR_PROJECT_PATH`), les conteneurs utilisent donc le
`radar.db` de l'hôte : lancer la commande ci-dessus en local, depuis la racine
du repo, suffit. Sauvegarder `radar.db` avant.

## Docker

    scripts/rebuild.sh radar-api

`scripts/rebuild.sh` reconstruit l'image sans cache et redémarre le service
(voir [`docs/operations.fr.md`](../docs/operations.fr.md)). `RADAR_API_KEY` et
`RADAR_PROJECT_PATH` doivent être définies dans l'environnement du shell ou
dans `.env` (référencées dans `docker-compose.yml`). `RADAR_PORTFOLIO_PATH` ne concerne que le profil CLI
séparé `radar-audit`.

`radar-api` est raccordée à l'instance Traefik partagée (même convention que
les autres projets `marvinlerouge`) : réseau externe `traefik-public`,
`Host(\`radar-api.marvinlerouge.local\`)` sur l'entrypoint `web` en local. Le
routeur de production (`radar-api.marvinlerouge.dev`, `websecure`/
`letsencrypt`) n'est pas encore raccordé, ce dépôt n'a pas de compose de
production pour l'instant. L'hôte du dashboard `radar.marvinlerouge.local`
route aussi `/api` vers `radar-api` (préfixe retiré).

## Badge de qualité

Tout dépôt audité par Engineering-Radar peut lier un badge
shields.io de type [endpoint](https://shields.io/badges/endpoint-badge) dans
son README, alimenté par `GET /repositories/{repository_id}/badge`. Rien
d'autre (aucun contenu de rapport, aucun score) n'est jamais écrit dans le
dépôt audité, seule cette ligne Markdown :

    [![Quality](https://img.shields.io/endpoint?url=https%3A%2F%2Fradar-api.marvinlerouge.dev%2Frepositories%2F{repository_id}%2Fbadge)](https://radar-api.marvinlerouge.dev/repositories/{repository_id}/report)

Remplacer `{repository_id}` par l'identifiant numérique du dépôt dans la base
de Radar. En local, remplacer le domaine par `radar-api.marvinlerouge.local`.

Le lien pointe toujours vers le point d'accès JSON brut `/report`. La page de
rapport lisible par un humain se trouve dans
[`radar-dashboard`](../radar-dashboard/README.fr.md), à l'adresse
`/repositories/<slug>-<id>`.

## Lancer les tests

    uv run --package radar-api pytest

## Limitations connues

- L'utilisation de `httpx` avec `starlette.testclient` émet actuellement un `DeprecationWarning` dans les tests (uniquement en test, aucun effet à l'exécution) ; aucune action nécessaire sauf changement de la pile de dépendances.
- Le service ne valide pas `RADAR_DATABASE_URL` / `RADAR_API_KEY` au démarrage, une valeur manquante ou mal configurée se traduit par un `500` (URL de base de données) ou un `401` sur chaque écriture (clé API) plutôt qu'un échec au démarrage. Suivi comme amélioration future.
- Le mode WAL de SQLite n'est pas encore activé, les lectures concurrentes de l'API et les écritures de `radar-audit` sur le même fichier de base de données peuvent occasionnellement provoquer une erreur "database is locked". Suivi comme amélioration future (concerne `radar-core`).
