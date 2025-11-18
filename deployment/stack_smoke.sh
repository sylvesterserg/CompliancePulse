#!/usr/bin/env bash
set -euo pipefail

# Full-stack validation script for production compose stack.
# - Builds images with no cache
# - Brings up stack
# - Validates NGINX config (nginx -t)
# - Verifies API health and NGINX forward health
# - Checks worker and scheduler logs for stability

COMPOSE_FILE="docker-compose.prod.yml"
STACK_NAME="compliancepulse-prod"
API_CTN="compliancepulse-api"
NGINX_CTN="compliancepulse-nginx"
WORKER_CTN="compliancepulse-worker"
SCHED_CTN="compliancepulse-scheduler"

compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  elif docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    echo "docker-compose or docker compose not found" >&2
    exit 1
  fi
}

echo "[stack] Tearing down existing stack (if any)"
compose -f "$COMPOSE_FILE" down || true

echo "[stack] Building images (no cache)"
compose -f "$COMPOSE_FILE" build --no-cache

echo "[stack] Starting stack"
compose -f "$COMPOSE_FILE" up -d

echo "[health] Waiting for API container to report healthy"
ATTEMPTS=20
SLEEP=3
for i in $(seq 1 $ATTEMPTS); do
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$API_CTN" 2>/dev/null || echo "unknown")
  if [ "$STATUS" = "healthy" ]; then
    break
  fi
  echo "  - attempt $i/$ATTEMPTS: api status=$STATUS"
  sleep $SLEEP
done

if [ "$STATUS" != "healthy" ]; then
  echo "[fail] API did not become healthy"
  docker logs "$API_CTN" --tail=200 || true
  exit 1
fi

echo "[lint] Validating NGINX config via nginx -t"
docker exec -i "$NGINX_CTN" nginx -t

echo "[health] Checking API health endpoint inside API container"
docker exec -i "$API_CTN" bash -lc "curl -sf http://localhost:8000/health"

echo "[health] Checking NGINX forward on host"
curl -sf http://localhost/api/health | grep -q '"healthy"' || {
  echo "[fail] NGINX forward route did not return healthy payload" >&2
  exit 1
}

echo "[auth] Validating UI login form action points to /api/auth/login"
curl -sf http://localhost/auth/login | grep -q '<form[^>]*action="/api/auth/login"' || {
  echo "[fail] UI login form action not pointing to /api/auth/login" >&2
  exit 1
}

echo "[auth] Testing API login via NGINX (/api/auth/login)"
JAR="/tmp/cp_cookies.txt"
rm -f "$JAR" || true
LOGIN_HTML=$(curl -sf -c "$JAR" http://localhost/api/auth/login)
CSRF_TOKEN=$(printf "%s" "$LOGIN_HTML" | sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p')
if [ -z "$CSRF_TOKEN" ]; then
  echo "[fail] Could not extract CSRF token from /api/auth/login" >&2
  exit 1
fi

# Use bootstrap admin credentials from defaults (matches .env)
ADMIN_EMAIL=${ADMIN_EMAIL:-demo@compliancepulse.io}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-ChangeMe123!}

# Perform login and validate redirect + session cookie
AUTH_RESP=$(curl -s -D - -o /dev/null -b "$JAR" -c "$JAR" -X POST \
  http://localhost/api/auth/login \
  -d "email=${ADMIN_EMAIL}&password=${ADMIN_PASSWORD}&csrf_token=${CSRF_TOKEN}")
printf "%s" "$AUTH_RESP" | grep -q "^HTTP/1.1 303" || {
  echo "[fail] API login did not return 303 redirect" >&2
  printf "%s\n" "$AUTH_RESP" >&2
  exit 1
}
printf "%s" "$AUTH_RESP" | tr -d '\r' | grep -qi "^location: /" || {
  echo "[fail] API login redirect Location header missing or incorrect" >&2
  printf "%s\n" "$AUTH_RESP" >&2
  exit 1
}
printf "%s" "$AUTH_RESP" | grep -qi "^set-cookie: .*cp_session=" || {
  echo "[fail] API login did not set session cookie" >&2
  printf "%s\n" "$AUTH_RESP" >&2
  exit 1
}

echo "[stability] Monitoring worker and scheduler for 30s"
sleep 30

echo "[logs] Checking for crashes or stack traces"
for c in "$API_CTN" "$NGINX_CTN" "$WORKER_CTN" "$SCHED_CTN"; do
  echo "  - scanning logs for $c"
  docker logs "$c" --tail=500 2>&1 | rg -n "(Traceback|Exception|ERROR)" && {
    echo "[fail] Detected errors in logs for $c" >&2
    exit 1
  } || true
done

echo "[success] All systems healthy"
