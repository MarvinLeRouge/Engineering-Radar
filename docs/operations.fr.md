🇫🇷 Version française | [🇬🇧 English version](operations.md)

---

# Opérations

Référence opérationnelle minimale. C'est un système local, mono-utilisateur,
offline-first : il n'y a pas encore de déploiement hébergé.

## Lancer les services

`radar-api` et `radar-dashboard` sont des services permanents démarrés
avec Docker Compose, depuis la racine du dépôt, une fois le `.env` rempli
à partir de `.env.example` :

```bash
docker compose up -d
```

- **Traefik** : les deux services rejoignent le réseau externe
  `traefik-public`, qui doit exister avant le premier démarrage (il
  appartient à l'installation Traefik locale, pas à ce projet). Le
  dashboard répond sur `radar.marvinlerouge.local`, qui route aussi `/api`
  vers `radar-api` ; l'API répond sur `radar-api.marvinlerouge.local` et
  sur le port 8000 de l'hôte.
- **Base partagée** : le volume `radar-data` est un bind mount de
  `RADAR_PROJECT_PATH` (le dossier du projet sur l'hôte) sur `/data` : les
  conteneurs lisent et écrivent donc le même `radar.db` qu'un `uv run`
  local.
- **Permissions** : les images Python tournent sous l'uid 1000. Le dossier
  hôte derrière `RADAR_PROJECT_PATH`, et `radar.db` lui-même, doivent être
  accessibles en écriture à l'uid 1000, sinon toute écriture (verdicts,
  statuts, notes) échoue.
- **Clé d'API** : les endpoints PATCH exigent `RADAR_API_KEY` dans
  l'en-tête `X-API-Key` ; la saisir dans la page Settings du dashboard
  (conservée pour la session du navigateur).

## Lancer l'audit

`radar-audit` est une CLI lancée à la demande, pas un service permanent.
La façon supportée de la lancer est en local, avec `uv`, sur le portfolio
de `~/projets` (`repos_root` dans `radar-audit/portfolio.yaml`) :

```bash
uv run radar-audit run some-repo   # lance les outils, stocke leurs résultats bruts
uv run radar-audit score some-repo # transforme le dernier audit en notes, constats et éléments de roadmap
```

Voir le [guide développeur](guides/developer_guide.fr.md) pour
l'installation, `--all`, `--dry-run` et la commande `report` (rapport
Markdown).

L'image Docker du profil `cli` (`docker compose --profile cli run --rm radar-audit`) ne peut
pas lancer un audit complet aujourd'hui : c'est une image Python slim sans
les outils externes appelés par de nombreux runners (Node/npx, Composer,
PHP, Docker...), et `~/projets` y désigne `/home/appuser/projets` alors que
le portfolio est monté sur `/portfolio`. Utiliser le lancement local.

## Données

Toutes les données d'audit structurées vivent dans la base de données
pointée par `RADAR_DATABASE_URL`. En usage local, il s'agit généralement
d'un fichier SQLite gitignored ; rien dans le schéma ne suppose SQLite
spécifiquement (géré via les migrations Alembic dans `radar-core`).

Les sorties brutes des outils capturées pendant une exécution sont
conservées à côté des résultats normalisés plutôt que jetées, afin qu'un
constat puisse toujours être retracé jusqu'à l'invocation d'outil qui l'a
produit.

Il n'y a pas encore d'automatisation de sauvegarde : sauvegarder
manuellement le fichier de base de données si son contenu compte pour
vous, et toujours avant d'appliquer des migrations.

Merger une pull request qui ajoute une migration Alembic ne l'applique pas
à votre `radar.db`. L'appliquer depuis la racine du dépôt, après une
sauvegarde :

```bash
cp radar.db "radar.db.bak-$(date +%Y%m%d%H%M%S)"
set -a && source .env && set +a
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
```

Les services ne migrent pas la base au démarrage.

## Reconstruire les images

Reconstruire les images Docker avec `scripts/rebuild.sh`, et non
`docker compose up --build` :

```
scripts/rebuild.sh                  # tous les services
scripts/rebuild.sh radar-dashboard  # un seul service
```

Le script lance `docker compose build --pull --no-cache` puis
`docker compose up -d`. `radar-audit` (service du profil `cli`) est aussi
reconstruit mais pas démarré, puisque c'est une CLI lancée à la demande et
non un service permanent. Chaque Dockerfile met à jour ses paquets système
(`apt-get upgrade` / `apk upgrade`), mais Docker réutilise cette étape depuis
son cache de build tant que le Dockerfile ne change pas : les correctifs de
sécurité publiés depuis le premier build n'arrivent donc jamais dans l'image.
`--pull` rafraîchit les images de base et `--no-cache` réexécute toutes les
étapes, au prix d'un rebuild plus lent (les dépendances sont réinstallées).

## Suivi des erreurs

Sentry est optionnel et désactivé tant qu'aucun DSN n'est défini (voir
`.env.example`). `SENTRY_BACKEND_DSN` est partagé par `radar-api` et la CLI
`radar-audit` ; `SENTRY_FRONTEND_DSN` est intégré au bundle de
`radar-dashboard` au build de l'image, le changer impose donc un rebuild.
`radar-audit` ne remonte que les crashs inattendus : les échecs d'outils et
les erreurs gérées par la CLI ne sont jamais envoyés. Aucune donnée
utilisateur, en-tête, corps de requête, query string ni variable de pile
n'est collectée.

Dans Docker, Compose transmet `SENTRY_BACKEND_DSN` à `radar-api` et
`radar-audit` sous le nom `SENTRY_DSN`, la variable que lit le code. Un
`uv run radar-audit` local ne remonte vers Sentry que si `SENTRY_DSN`
lui-même est exporté dans le shell : sourcer le `.env` définit
`SENTRY_BACKEND_DSN`, pas `SENTRY_DSN`.

## Logs

`radar-api` et `radar-audit` écrivent des **logs structurés** avec structlog : chaque ligne est un événement avec des champs nommés, écrit sur **stderr** (stdout reste réservé à l'affichage propre à la CLI, comme les plans `--dry-run` et les rapports).

- **Format** : lignes JSON dans Docker ou toute sortie qui n'est pas un terminal, texte coloré lisible dans un terminal. Forcer l'un ou l'autre avec `RADAR_LOG_FORMAT=json` ou `RADAR_LOG_FORMAT=console`.
- **Niveau** : `RADAR_LOG_LEVEL` (`debug`, `info`, `warning`, `error`), `info` par défaut.
- **Jamais journalisés** : les paramètres de requête, les en-têtes (la clé d'API passe dans l'un d'eux), les corps de requête.

| Événement | Émis par | Champs |
|---|---|---|
| `request_handled` | radar-api, un par requête HTTP (niveau error pour les 5xx) | `method`, `path`, `status`, `duration_ms` |
| `audit_started` | radar-audit `run` | `repo`, `subprojects` |
| `tool_finished` | radar-audit, un par exécution d'outil | `tool`, `subproject`, `exit_code`, `duration_ms`, `audit_id` |
| `tool_crashed` | radar-audit, niveau error, quand un outil lève une exception | `tool`, `target`, `error`, `audit_id` |
| `audit_finished` | radar-audit `run` | `repo`, `tools_run`, `duration_ms`, `audit_id` |
| `scoring_finished` | radar-audit `score` | `repo`, `global_score`, `findings`, `audit_id` |

Chaque ligne écrite pendant un audit porte son `audit_id`, ce qui permet d'isoler un audit entier. Chaque ligne a aussi un `timestamp` (UTC, ISO 8601) et un `level`.

Les lire en local :

```bash
docker compose logs -f radar-api
# seulement les erreurs serveur, en JSON compact :
docker compose logs --no-log-prefix radar-api | jq -c 'select(.level == "error")'
# les outils les plus lents d'un audit lancé dans un terminal :
RADAR_LOG_FORMAT=json uv run radar-audit run some-repo 2>&1 >/dev/null \
  | jq -s 'map(select(.event == "tool_finished")) | sort_by(-.duration_ms) | .[:5]'
```

**Logs et Sentry sont complémentaires.** Sentry (ci-dessus) collecte les *erreurs* : exceptions regroupées, stack traces, alertes. Les logs enregistrent *tout ce qui se passe*, y compris quand rien ne plante : durées, décisions, étapes. Quand Sentry est activé, les dernières lignes de log sont jointes à chaque erreur qu'il remonte, sous forme de fil d'Ariane (breadcrumbs). Pour chercher dans les logs sur plusieurs jours ou construire des tableaux de bord, voir le [guide d'agrégation des logs](guides/log-aggregation.fr.md) (Loki et Grafana, optionnels, hors de la stack du projet).

## CI / automatisation

- `CHANGELOG.md` est régénéré principalement par un hook local `post-commit` intégré au framework `pre-commit` (`scripts/changelog-post-commit.sh`, exécute git-cliff et intègre le résultat dans le même commit), si bien que les PR de fonctionnalité contiennent déjà leur propre entrée de changelog
- En secours, [`.github/workflows/changelog.yml`](../.github/workflows/changelog.yml) régénère toujours `CHANGELOG.md` à chaque push sur `main` et ouvre une pull request (ne pousse jamais directement sur `main`), au cas où un commit atterrirait sans passer par le hook local
- Les hooks pre-commit tournent en local à chaque commit : `ruff`, `ruff-format` et `mypy` par package Python, et les vérifications de lint, de format et de types du dashboard
- La CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) s'exécute à chaque push et pull request vers `main` : les tests de chaque package avec un seuil de couverture de 80 %, les vérifications de lint, de format et de types du dashboard, et ses tests end-to-end Playwright. Le lint et la vérification de types Python ne tournent que dans pre-commit. Détails dans le [guide développeur](guides/developer_guide.fr.md#pipeline-ci) et [`CONTRIBUTING.md`](i18n/fr/CONTRIBUTING.fr.md)

## Secrets

Le moteur d'audit lit les dépôts locaux en lecture seule et ne nécessite
aucun identifiant ni clé d'API pour son périmètre actuel. Si un futur
critère nécessite un accès réseau ou une clé d'API, celui-ci devra être
opt-in et explicitement signalé (voir la décision sur l'accès réseau dans
[`docs/adr/`](adr/)).
