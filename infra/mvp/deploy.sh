#!/usr/bin/env bash
# ONEVO MVP — pull ACR images and restart the stack on the Azure VM.
# Invoked by GitHub Actions, Jenkins, or manually on the VM.
#
# Env:
#   ONEVO_DIR     — app root (default /opt/onevo/app)
#   USE_GPU       — "true" to include docker-compose.gpu.yml (default false on CPU VM)
#   DEPLOY_MODE   — "acr" (pull pre-built images) or "local" (build on VM)
set -euo pipefail

ONEVO_DIR="${ONEVO_DIR:-/opt/onevo/app}"
DEPLOY_MODE="${DEPLOY_MODE:-acr}"

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
if [[ "${USE_GPU:-false}" == "true" ]]; then
  COMPOSE_FILES+=" -f docker-compose.gpu.yml"
fi
if [[ "$DEPLOY_MODE" == "acr" ]]; then
  COMPOSE_FILES+=" -f docker-compose.acr.yml"
fi

cd "$ONEVO_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: Missing $ONEVO_DIR/.env — copy from infra/mvp/.env.production.example and fill secrets."
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

if [[ "$DEPLOY_MODE" == "acr" ]]; then
  : "${ONEVO_BACKEND_IMAGE:?Set ONEVO_BACKEND_IMAGE}"
  : "${ONEVO_DASHBOARD_IMAGE:?Set ONEVO_DASHBOARD_IMAGE}"
  : "${ONEVO_CLOUD_AI_IMAGE:?Set ONEVO_CLOUD_AI_IMAGE}"

  if [[ -n "${ACR_LOGIN_SERVER:-}" && -n "${ACR_USERNAME:-}" && -n "${ACR_PASSWORD:-}" ]]; then
    echo "$ACR_PASSWORD" | docker login "$ACR_LOGIN_SERVER" -u "$ACR_USERNAME" --password-stdin
  fi

  echo "==> Pulling images from ACR..."
  docker compose $COMPOSE_FILES pull backend dashboard cloud-ai

  echo "==> Starting stack (ACR images)..."
  docker compose $COMPOSE_FILES up -d --no-build --remove-orphans
else
  echo "==> Building images on VM..."
  docker compose $COMPOSE_FILES build backend dashboard cloud-ai

  echo "==> Starting stack (local build)..."
  docker compose $COMPOSE_FILES up -d --remove-orphans
fi

echo "==> Waiting for backend health..."
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8081/api/health" >/dev/null; then
    echo "Backend healthy."
    docker compose ps
    exit 0
  fi
  sleep 2
done

echo "ERROR: Backend did not become healthy in time."
docker compose logs backend --tail 80
exit 1
