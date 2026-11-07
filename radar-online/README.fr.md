🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# radar-online

Service hébergé d'[Engineering-Radar](../README.fr.md) qui publie des rapports
expurgés : le score global et les scores par catégorie d'un dépôt, ses
tendances et un badge, sans aucun finding. Décisions dans
l'[ADR 0014](../docs/adr/0014-radar-online-public-reports.md), conception dans
[radar-online design](../docs/radar-online-design.md) (en anglais).

**Statut :** socle uniquement (CHORE-010). L'application démarre et répond à
`GET /api/health` ; les comptes, la publication, les pages publiques et le
badge sont les prochaines tâches de la
[section 9 de la roadmap](../docs/roadmap.fr.md).

## Organisation

- `src/radar_online/` : application FastAPI (`main.py`), configuration, session
  de base de données, et `models/` (ses propres tables uniquement, jamais les
  données d'audit de radar-core).
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

## Docker

    scripts/rebuild.sh radar-online

En local, Traefik l'expose sur `radar-online.marvinlerouge.local/api`, avec sa
base dans `<RADAR_PROJECT_PATH>/radar-online.db` (le bind mount partagé
`radar-data`). Le conteneur ne migre pas au démarrage : lancer d'abord la
commande Alembic ci-dessus. Le déploiement hébergé sur `radar.marvinlerouge.dev`
arrive avec CHORE-012.
