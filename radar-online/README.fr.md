🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# radar-online

Service hébergé d'[Engineering-Radar](../README.fr.md) qui publie des rapports
expurgés : le score global et les scores par catégorie d'un dépôt, ses
tendances et un badge, sans aucun finding. Décisions dans
l'[ADR 0014](../docs/adr/0014-radar-online-public-reports.md), conception dans
[radar-online design](../docs/radar-online-design.md) (en anglais).

**Statut :** modèle de données en place (FEAT-037) : utilisateurs, clés d'API
hachées, jetons d'action à usage unique, dépôts et rapports publiés, plus le
contrat de payload partagé `radar_core.publication` ; les comptes sont créés
par une commande admin (FEAT-050) et les rapports sont envoyés par
`POST /api/reports` (FEAT-042). Les pages publiques et le badge sont les
prochaines tâches de la
[section 9 de la roadmap](../docs/roadmap.fr.md).

## Organisation

- `src/radar_online/` : application FastAPI (`main.py`), configuration, session
  de base de données, `models/` (ses propres tables uniquement, jamais les
  données d'audit de radar-core), `tokens.py` (clés et jetons aléatoires,
  stockés sous forme de hachages SHA-256), `accounts.py` et `cli.py` (la
  commande admin `radar-online`), `auth.py` (vérification de la clé d'API) et
  `routers/` (les endpoints de l'API).
- `alembic/` : les migrations propres à radar-online, sur sa propre base SQLite.
- `tests/` : chaque test tourne sur un fichier SQLite jetable et migré.

Toutes les routes, le schéma OpenAPI (`/api/openapi.json`) et la documentation
(`/api/docs`) sont sous `/api`, puisque le dashboard online est servi sur le
même hôte.

## Configuration

- `RADAR_ONLINE_DATABASE_URL` (obligatoire) : l'URL SQLite, jamais supposée.
- Optionnelles, comme pour radar-api : `SENTRY_DSN`, `SENTRY_ENVIRONMENT`,
  `RADAR_LOG_LEVEL`, `RADAR_LOG_FORMAT` (voir
  l'[exploitation](../docs/operations.fr.md)).

## Développement

Depuis la racine du dépôt :

    set -a && source .env && set +a
    uv run --package radar-online alembic -c radar-online/alembic.ini upgrade head
    uv run --package radar-online uvicorn radar_online.main:app --reload --port 8010

Tests :

    uv run --package radar-online pytest radar-online/tests --cov=radar_online

## Créer un compte

Tant que l'inscription par email n'existe pas, l'admin crée chaque compte,
actif d'emblée, avec sa première clé d'API :

    uv run --package radar-online radar-online create-account \
        --email ada@example.com --display-name "Ada" --slug ada

Sous Docker : `docker compose exec radar-online radar-online create-account ...`.
La clé est affichée une seule fois et seul son hachage est stocké : la
transmettre à son propriétaire sans la conserver ailleurs. Le slug est l'espace
de noms public (1 à 64 lettres minuscules, chiffres ou tirets) ; l'email et le
slug doivent être libres.

## Envoyer un rapport

`POST /api/reports` avec l'en-tête `X-API-Key` et, en corps JSON, un payload de
publication v1 (`radar_core.publication`, champs inconnus refusés) de 64 Kio au
plus. Le dépôt est créé au premier envoi, dans l'espace de noms du propriétaire
de la clé ; renvoyer un commit déjà publié remplace son rapport (200), sinon le
rapport est ajouté (201). La réponse donne le chemin de la page publique, par
exemple `{"report_path": "/u/ada/summit-stats"}`. Une clé absente, inconnue ou
révoquée, ou un compte inactif, reçoit une 401.

## Docker

    scripts/rebuild.sh radar-online

En local, Traefik l'expose sur `radar-online.marvinlerouge.local/api`, avec sa
base dans `<RADAR_PROJECT_PATH>/radar-online.db` (le bind mount partagé
`radar-data`). Le conteneur ne migre pas au démarrage : lancer d'abord la
commande Alembic ci-dessus. Le déploiement hébergé sur `radar.marvinlerouge.dev`
arrive avec CHORE-012.
