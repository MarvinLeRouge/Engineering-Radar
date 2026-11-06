🇫🇷 Version française | [🇬🇧 English version](log-aggregation.md)

---

# Agrégation des logs avec Loki et Grafana (optionnel)

> **Statut : tutoriel, non testé de bout en bout.** La configuration ci-dessous suit la documentation officielle de Grafana (Loki 3.7, Alloy, Grafana) au 2026-11-04, mais elle n'a pas été exécutée sur ce projet. Elle **ne fait pas partie de la stack du projet** : rien ici n'est nécessaire pour utiliser Engineering-Radar.

`radar-api` et `radar-audit` écrivent déjà des logs JSON structurés sur stderr (voir [opérations, Logs](../operations.fr.md#logs)). `docker compose logs` et `jq` suffisent pour les lire sur le moment. Ce guide ajoute ce qu'ils ne savent pas faire : chercher sur plusieurs jours et à travers les redémarrages, filtrer par champ, et tracer des graphiques.

## 1. Les trois briques

| Brique | Rôle | Analogie |
|---|---|---|
| **Grafana Alloy** | Collecteur : lit les logs de chaque conteneur via le socket Docker, extrait quelques champs JSON en labels, envoie les lignes à Loki | le facteur |
| **Loki** | Stockage : conserve les lignes de log, indexées seulement par leurs labels (pas en texte intégral, ce qui le garde léger) | les archives |
| **Grafana** | Interface : interroge Loki en LogQL, affiche lignes et graphiques, construit des tableaux de bord | la salle de lecture |

Promtail, l'ancien collecteur de Loki, est déprécié au profit d'Alloy.

**Labels contre champs.** Loki n'indexe que les **labels** : il faut donc en garder peu, avec peu de valeurs possibles (nom du conteneur, `level`, `event`). Les valeurs très variées (`audit_id`, `path`, `duration_ms`) restent dans la ligne JSON et sont lues au moment de la requête avec `| json`. Faire de `audit_id` un label créerait un flux d'index par audit et ralentirait tout.

## 2. Fichiers

Créer un dossier **en dehors** du dépôt, par exemple `~/projets/observability/`, avec cette arborescence :

```
observability/
├── docker-compose.yml
├── loki-config.yaml
├── config.alloy
└── grafana-datasources.yaml
```

### `docker-compose.yml`

Grafana est publié via Traefik sur `grafana.marvinlerouge.local`, comme les services radar (ajouter l'hôte dans `/etc/hosts` de la même façon). Loki et Alloy restent sur le réseau interne.

```yaml
services:
  loki:
    image: grafana/loki:3.7.0
    command: -config.file=/etc/loki/config.yaml
    volumes:
      - ./loki-config.yaml:/etc/loki/config.yaml:ro
      - loki-data:/loki
    networks: [default]

  alloy:
    image: grafana/alloy:latest
    command:
      - run
      - --server.http.listen-addr=0.0.0.0:12345
      - --storage.path=/var/lib/alloy/data
      - /etc/alloy/config.alloy
    volumes:
      - ./config.alloy:/etc/alloy/config.alloy:ro
      # Accès en lecture seule à l'API Docker : cela donne beaucoup de pouvoir, à garder en local.
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on: [loki]
    networks: [default]

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    volumes:
      - ./grafana-datasources.yaml:/etc/grafana/provisioning/datasources/datasources.yaml:ro
      - grafana-data:/var/lib/grafana
    depends_on: [loki]
    networks: [default, traefik-public]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.grafana.rule=Host(`grafana.marvinlerouge.local`)"
      - "traefik.http.routers.grafana.entrypoints=web"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"

volumes:
  loki-data:
  grafana-data:

networks:
  traefik-public:
    external: true
```

L'accès admin anonyme n'est acceptable que parce que ce Grafana est local et mono-utilisateur ; ne jamais l'exposer ainsi.

### `loki-config.yaml`

Dérivé du `loki-local-config.yaml` fourni par Loki (processus unique, stockage sur disque), avec le stockage déplacé dans le volume `/loki`, 7 jours de rétention et l'envoi de statistiques d'usage désactivé.

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2026-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 168h # 7 jours

compactor:
  working_directory: /loki/retention
  delete_request_store: filesystem
  retention_enabled: true

analytics:
  reporting_enabled: false
```

### `config.alloy`

Découvre les conteneurs, ne garde que ceux de radar, étiquette chaque ligne avec son conteneur, son niveau et son événement, puis l'envoie à Loki.

```alloy
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

discovery.relabel "radar" {
  targets = discovery.docker.containers.targets

  // Ne garder que les conteneurs de ce projet.
  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/engineering-radar-radar-.*"
    action        = "keep"
  }

  // Les noms Docker commencent par "/" : stocker "engineering-radar-radar-api-1" comme label container.
  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container"
  }
}

loki.source.docker "radar" {
  host          = "unix:///var/run/docker.sock"
  targets       = discovery.relabel.radar.output
  relabel_rules = discovery.relabel.radar.rules
  forward_to    = [loki.process.radar.receiver]
}

loki.process "radar" {
  forward_to = [loki.write.local.receiver]

  // Les lignes sont en JSON (logs radar) ; une ligne non JSON est gardée telle quelle.
  stage.json {
    expressions = { level = "", event = "" }
  }

  // Seulement des champs à faible nombre de valeurs. audit_id, path, duration_ms restent dans la ligne.
  stage.labels {
    values = { level = "", event = "" }
  }
}

loki.write "local" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

`event` est un label raisonnable ici, parce que radar n'écrit qu'une poignée de noms d'événements fixes. Les lignes de démarrage d'uvicorn utilisent leur message comme `event`, ce qui ajoute quelques valeurs ; si cela gêne, retirer `event` de `stage.labels` et filtrer plutôt avec `| json | event="..."`.

### `grafana-datasources.yaml`

```yaml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
```

## 3. Démarrer et vérifier

```bash
cd ~/projets/observability
docker compose up -d
docker compose ps
```

- Loki est prêt : `docker compose exec loki wget -qO- http://localhost:3100/ready` affiche `ready`.
- L'interface d'Alloy (graphe des composants, erreurs) n'est pas publiée par défaut : ajouter `ports: ["12345:12345"]` au service alloy pour ouvrir http://localhost:12345.
- Grafana : http://grafana.marvinlerouge.local, puis **Explore** avec la source de données Loki.

Pour générer quelques lignes, ouvrir le dashboard ou appeler l'API : chaque requête écrit une ligne `request_handled`. Les logs ne sont collectés que depuis les **conteneurs** : un audit lancé avec `uv run radar-audit` dans un terminal écrit dans ce terminal, pas dans Docker, et Loki ne le voit donc jamais.

## 4. Requêtes LogQL à essayer

LogQL se lit comme une chaîne de traitement : un sélecteur de labels entre accolades, puis des filtres et des analyseurs.

```logql
# Tout ce qui vient de l'API
{container="engineering-radar-radar-api-1"}

# Tous les plantages d'outils, tous audits confondus
{level="error", event="tool_crashed"}

# Les erreurs serveur de l'API
{container="engineering-radar-radar-api-1", level="error"} | json

# Un audit de bout en bout (remplacer 52 par un vrai audit_id)
{container=~"engineering-radar-radar-.*"} | json | audit_id="52"

# Les requêtes lentes : plus de 500 ms
{event="request_handled"} | json | duration_ms > 500

# Durée moyenne par outil sur les dernières 24 heures (requête métrique : utiliser la vue graphique)
avg by (tool) (avg_over_time({event="tool_finished"} | json | unwrap duration_ms [24h]))

# Requêtes par minute, par statut
sum by (status) (count_over_time({event="request_handled"} | json [1m]))
```

Depuis Explore, **Add to dashboard** transforme n'importe laquelle de ces requêtes en panneau.

## 5. Disque, rétention, suppression

- La rétention est de 7 jours (`retention_period` dans `loki-config.yaml`) ; le compactor supprime les données plus anciennes. Vérifier l'espace utilisé avec `docker system df -v | grep loki-data`.
- Arrêter : `docker compose down` (les données restent dans les volumes).
- Tout supprimer, y compris les logs stockés et les réglages Grafana : `docker compose down -v`. Cela supprime les volumes `loki-data` et `grafana-data`, sans retour possible.

## 6. Aller plus loin

- **Alertes** : les alertes Grafana sur une requête LogQL (par exemple, tout `tool_crashed` dans la dernière heure).
- **Métriques** : Prometheus ou Grafana Mimir pour les séries numériques, à côté de Loki pour les logs ; Alloy sait collecter les deux.
- **Traces** : Grafana Tempo avec OpenTelemetry, pour suivre une requête à travers plusieurs services. Le `audit_id` des logs radar est un premier pas manuel dans cette direction.
