#!/usr/bin/env bash
# Rebuild and restart the Docker Compose services without any build cache.
# A cached `apt-get upgrade` / `apk upgrade` layer would keep shipping
# packages from the day it was first built, so security fixes published
# since then would never reach the image.
# Usage: scripts/rebuild.sh [service...]   (no argument: every service)
set -euo pipefail

cd "$(dirname "$0")/.."
docker compose build --pull --no-cache "$@"
docker compose up -d "$@"
