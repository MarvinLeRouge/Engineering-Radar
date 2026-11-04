#!/usr/bin/env bash
# Rebuild and restart the Docker Compose services without any build cache.
# A cached `apt-get upgrade` / `apk upgrade` layer would keep shipping
# packages from the day it was first built, so security fixes published
# since then would never reach the image.
# Usage: scripts/rebuild.sh [service...]   (no argument: every service)
set -euo pipefail

cd "$(dirname "$0")/.."

# `--profile cli` so radar-audit (a CLI, not a long-running service) is rebuilt too.
docker compose --profile cli build --pull --no-cache "$@"

# Only long-running services are restarted: starting radar-audit would just run the CLI once.
if [ "$#" -eq 0 ]; then
  docker compose up -d
  exit 0
fi
long_running=$(docker compose config --services)
to_start=()
for service in "$@"; do
  if grep -qx "$service" <<<"$long_running"; then
    to_start+=("$service")
  fi
done
if [ "${#to_start[@]}" -gt 0 ]; then
  docker compose up -d "${to_start[@]}"
fi
