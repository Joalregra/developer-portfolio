#!/usr/bin/env bash
# Runs on the server. The GitHub Actions key can run only this script (forced SSH command, see
# docs/deploy.md), so treat it as production code. Safe to run more than once.
#
# It does not run database migrations: those are a deliberate manual step, from a developer
# machine with the Neon owner URL, which never lives on the server.
set -euo pipefail

REPO_DIR="${HOME}/portfolio"

if ! docker network inspect web >/dev/null 2>&1; then
  echo "The Docker network 'web' does not exist. Create it first (docs/deploy.md)." >&2
  exit 1
fi

git -C "$REPO_DIR" pull --ff-only

# Shared proxy: bring it up if needed and reload the Caddyfile (no restart, no dropped connections).
cd "$REPO_DIR/deploy/proxy"
docker compose up -d
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile

# API: pull the image CI published and replace the container if it changed.
cd "$REPO_DIR/deploy/api"
docker compose pull api
docker compose up -d --remove-orphans api

docker image prune -f
echo "deploy finished"
