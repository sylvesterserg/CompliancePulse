#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[build] CompliancePulse build and release"

# Detect container engine
ENGINE="docker"
if ! command -v docker >/dev/null 2>&1 && command -v podman >/dev/null 2>&1; then
  ENGINE="podman"
fi
COMPOSE_CMD="${ENGINE} compose"

# Determine version
VERSION_FILE="${ROOT_DIR}/VERSION"
if [[ -f "$VERSION_FILE" ]]; then
  VERSION="$(cat "$VERSION_FILE" | tr -d ' \n')"
else
  VERSION=$(rg -n "version:\s*\"([0-9.]+)\"" -or '$1' backend/app/config.py 2>/dev/null || true)
  VERSION=${VERSION:-0.0.0-dev}
fi
echo "[build] Version: $VERSION"

IMAGE_REPO_DEFAULT="compliancepulse-backend"
IMAGE_REPO="${IMAGE_REPO:-$IMAGE_REPO_DEFAULT}"
REGISTRY="${REGISTRY:-}"
IMAGE_TAG="$IMAGE_REPO:$VERSION"
IMAGE_LATEST="$IMAGE_REPO:latest"
if [[ -n "$REGISTRY" ]]; then
  IMAGE_TAG="$REGISTRY/$IMAGE_TAG"
  IMAGE_LATEST="$REGISTRY/$IMAGE_LATEST"
fi

echo "[build] Building backend image: $IMAGE_TAG"
${ENGINE} build -f backend/Dockerfile -t "$IMAGE_TAG" -t "$IMAGE_LATEST" .

echo "[build] Validating compose file"
if [[ -f docker-compose.prod.yml ]]; then
  ${COMPOSE_CMD} -f docker-compose.prod.yml config >/dev/null
elif [[ -f podman-compose.prod.yml ]]; then
  ${COMPOSE_CMD} -f podman-compose.prod.yml config >/dev/null
else
  echo "No production compose file found" >&2
  exit 1
fi

if [[ -n "$REGISTRY" ]]; then
  echo "[push] Pushing images to $REGISTRY"
  ${ENGINE} push "$IMAGE_TAG"
  ${ENGINE} push "$IMAGE_LATEST"
else
  echo "[push] REGISTRY not set; skipping push"
fi

echo "[summary] Build artifacts"
echo "  Engine:       $ENGINE"
echo "  Image:        $IMAGE_TAG"
echo "  Latest tag:   $IMAGE_LATEST"
echo "  Compose file: $( [[ -f docker-compose.prod.yml ]] && echo docker-compose.prod.yml || echo podman-compose.prod.yml )"

