[🇫🇷 Version française](log-aggregation.fr.md) | 🇬🇧 English version

---

# Log aggregation with Loki and Grafana (optional)

> **Status: tutorial, not tested end to end.** The configuration below follows the official Grafana documentation (Loki 3.7, Alloy, Grafana) as of 2026-11-04, but it has not been run against this project. It is **not part of the project's stack**: nothing here is required to use Engineering-Radar.

`radar-api` and `radar-audit` already write structured JSON logs to stderr (see [operations, Logging](../operations.md#logging)). `docker compose logs` and `jq` are enough to read them on the spot. This guide adds what they cannot do: search across days and restarts, filter by field, and chart the results.

## 1. The three pieces

| Piece | Role | Analogy |
|---|---|---|
| **Grafana Alloy** | Collector: reads each container's logs through the Docker socket, extracts a few JSON fields as labels, ships the lines to Loki | the postman |
| **Loki** | Storage: keeps the log lines, indexed only by their labels (not by full text, which keeps it light) | the archive |
| **Grafana** | Interface: queries Loki with LogQL, shows lines and charts, builds dashboards | the reading room |

Promtail, Loki's former collector, is deprecated in favor of Alloy.

**Labels vs fields.** Loki indexes **labels** only, so keep them few and low-cardinality: container name, `level`, `event`. High-cardinality values (`audit_id`, `path`, `duration_ms`) stay inside the JSON line and are parsed at query time with `| json`. Turning `audit_id` into a label would create one index stream per audit and slow everything down.

## 2. Files

Create a folder **outside** the repository, for example `~/projets/observability/`, with this layout:

```
observability/
├── docker-compose.yml
├── loki-config.yaml
├── config.alloy
└── grafana-datasources.yaml
```

### `docker-compose.yml`

Grafana is published through Traefik on `grafana.marvinlerouge.local`, like the radar services (add the host to `/etc/hosts` the same way). Loki and Alloy stay on the internal network.

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
      # Read-only access to the Docker API: this grants a lot of power, keep it local.
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

Anonymous admin access is acceptable only because this Grafana is local and single-user; never expose it like this.

### `loki-config.yaml`

Derived from Loki's own `loki-local-config.yaml` (single process, filesystem storage), with storage moved to the `/loki` volume, 7 days of retention and usage reporting disabled.

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
  retention_period: 168h # 7 days

compactor:
  working_directory: /loki/retention
  delete_request_store: filesystem
  retention_enabled: true

analytics:
  reporting_enabled: false
```

### `config.alloy`

Discovers the containers, keeps only the radar ones, labels each line with its container, level and event, then ships it to Loki.

```alloy
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

discovery.relabel "radar" {
  targets = discovery.docker.containers.targets

  // Keep only this project's containers.
  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/engineering-radar-radar-.*"
    action        = "keep"
  }

  // Docker names start with "/": store "engineering-radar-radar-api-1" as the container label.
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

  // Lines are JSON (radar logs); a non-JSON line is kept as is.
  stage.json {
    expressions = { level = "", event = "" }
  }

  // Low-cardinality fields only. audit_id, path, duration_ms stay in the line.
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

`event` is a reasonable label here because radar logs a handful of fixed event names. Uvicorn's startup lines use their message as `event`, which adds a few extra values; if that bothers you, drop `event` from `stage.labels` and filter with `| json | event="..."` instead.

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

## 3. Start and check

```bash
cd ~/projets/observability
docker compose up -d
docker compose ps
```

- Loki is ready: `docker compose exec loki wget -qO- http://localhost:3100/ready` prints `ready`.
- Alloy's own UI (graph of components, errors): `docker compose port alloy 12345` is not published by default; add `ports: ["12345:12345"]` to the alloy service to open http://localhost:12345.
- Grafana: http://grafana.marvinlerouge.local, then **Explore** with the Loki data source.

Generate some lines: open the dashboard, or run an audit in Docker (`docker compose --profile cli run --rm radar-audit run some-repo` from the Engineering-Radar folder). Logs are only collected from **containers**: an audit run with `uv run radar-audit` in a terminal writes to that terminal, not to Docker, so Loki never sees it.

## 4. LogQL queries to try

LogQL reads like a pipeline: a label selector in braces, then filters and parsers.

```logql
# Everything from the API
{container="engineering-radar-radar-api-1"}

# Every tool crash, all audits
{level="error", event="tool_crashed"}

# API server errors
{container="engineering-radar-radar-api-1", level="error"} | json

# One audit end to end (replace 52 with a real audit_id)
{container=~"engineering-radar-radar-.*"} | json | audit_id="52"

# Slow requests: over 500 ms
{event="request_handled"} | json | duration_ms > 500

# Average tool duration per tool over the last 24 hours (a metric query: use the chart view)
avg by (tool) (avg_over_time({event="tool_finished"} | json | unwrap duration_ms [24h]))

# Requests per minute, by status
sum by (status) (count_over_time({event="request_handled"} | json [1m]))
```

From Explore, **Add to dashboard** turns any of these into a panel.

## 5. Disk, retention, removal

- Retention is 7 days (`retention_period` in `loki-config.yaml`); the compactor deletes older data. Check usage with `docker system df -v | grep loki-data`.
- Stop: `docker compose down` (data kept in the volumes).
- Remove everything, including stored logs and Grafana settings: `docker compose down -v`. This deletes the `loki-data` and `grafana-data` volumes and cannot be undone.

## 6. Going further

- **Alerts**: Grafana alerting on a LogQL query (for example, any `tool_crashed` in the last hour).
- **Metrics**: Prometheus or Grafana Mimir for numeric time series, next to Loki for logs; Alloy can collect both.
- **Traces**: Grafana Tempo with OpenTelemetry, to follow one request across services. The `audit_id` in radar's logs is a first, manual step in that direction.
