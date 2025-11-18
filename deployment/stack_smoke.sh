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

echo "[ui] Checking UI login route returns 200"
code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/auth/login)
[ "$code" = "200" ] || {
  echo "[fail] /auth/login returned $code (expected 200)" >&2
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

echo "[assets] Verifying static assets are served"
curl -sI http://localhost/static/css/app.css | head -n1 | grep -q " 200 " || {
  echo "[fail] Static CSS not served correctly" >&2
  exit 1
}

echo "[ui] Fetching dashboard with session cookie (should be HTML, 200)"
curl -s -b "$JAR" -D /tmp/dash_headers.txt -o /tmp/dash_body.html http://localhost/dashboard >/dev/null
head -n1 /tmp/dash_headers.txt | grep -q " 200 " || {
  echo "[fail] /dashboard did not return HTTP 200" >&2
  cat /tmp/dash_headers.txt >&2 || true
  exit 1
}
grep -q "<!DOCTYPE html>" /tmp/dash_body.html || {
  echo "[fail] /dashboard did not return HTML content" >&2
  head -n 20 /tmp/dash_body.html >&2 || true
  exit 1
}

echo "[ui] Rules page + modal + create"
curl -s -b "$JAR" -D /tmp/rules_hdrs.txt -o /tmp/rules.html http://localhost/rules >/dev/null
head -n1 /tmp/rules_hdrs.txt | grep -q " 200 " || { echo "[fail] /rules not 200" >&2; exit 1; }
RULES_MODAL=$(curl -sf -b "$JAR" http://localhost/rules/modal/new)
RULES_CSRF=$(printf "%s" "$RULES_MODAL" | sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p')
BENCH_ID=$(printf "%s" "$RULES_MODAL" | sed -n 's/.*<option value=\"\([^\"]*\)\">.*/\1/p' | head -n1)
if [ -n "$RULES_CSRF" ] && [ -n "$BENCH_ID" ]; then
  RULE_ID="SMOKE-RULE-$(date +%s)"
  CREATE_RULE_RESP=$(curl -s -b "$JAR" -X POST http://localhost/rules/create \
    -d "rule_id=$RULE_ID&benchmark_id=$BENCH_ID&title=Smoke%20Rule&severity=low&tags=&description=&remediation=&command=echo%201&expect_value=1&csrf_token=$RULES_CSRF")
  echo "$CREATE_RULE_RESP" | grep -q 'id="rules-table"' || {
    echo "[fail] Creating rule did not return updated rules table" >&2
    exit 1
  }
else
  echo "[warn] Could not parse Rules modal CSRF/benchmark; skipping create"
fi

echo "[ui] Scans page + modal + trigger"
curl -s -b "$JAR" -D /tmp/scans_hdrs.txt -o /tmp/scans.html http://localhost/scans >/dev/null
head -n1 /tmp/scans_hdrs.txt | grep -q " 200 " || { echo "[fail] /scans not 200" >&2; exit 1; }
SCANS_MODAL=$(curl -sf -b "$JAR" http://localhost/scans/modal/trigger)
SCANS_CSRF=$(printf "%s" "$SCANS_MODAL" | sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p')
SCANS_BID=$(printf "%s" "$SCANS_MODAL" | sed -n 's/.*<option value=\"\([^\"]*\)\">.*/\1/p' | head -n1)
if [ -n "$SCANS_CSRF" ] && [ -n "$SCANS_BID" ]; then
  TRIGGER_RESP=$(curl -s -b "$JAR" -X POST http://localhost/scans/trigger \
    -d "hostname=smoke-host&ip=&benchmark_id=$SCANS_BID&tags=&csrf_token=$SCANS_CSRF")
  echo "$TRIGGER_RESP" | grep -q 'id="scans-table"' || {
    echo "[fail] Triggering scan did not return updated scans table" >&2
    exit 1
  }
else
  echo "[warn] Could not parse Scans modal CSRF/benchmark; skipping trigger"
fi

echo "[ui] Schedule modal + create (if groups present)"
SCHED_MODAL=$(curl -sf -b "$JAR" http://localhost/automation/modal/schedule)
SCHED_CSRF=$(printf "%s" "$SCHED_MODAL" | sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p')
GROUP_ID=$(printf "%s" "$SCHED_MODAL" | sed -n 's/.*<option value=\"\([^\"]*\)\">.*/\1/p' | grep -E "^[0-9]+$" | head -n1 || true)
if [ -n "$SCHED_CSRF" ] && [ -n "$GROUP_ID" ]; then
  NAME="Smoke Schedule $(date +%s)"
  SCHED_RESP=$(curl -s -b "$JAR" -X POST http://localhost/automation/schedules \
    -d "name=$NAME&group_id=$GROUP_ID&frequency=daily&interval_minutes=&csrf_token=$SCHED_CSRF")
  echo "$SCHED_RESP" | grep -q 'id="schedules-panel"' || {
    echo "[fail] Creating schedule did not return updated schedules panel" >&2
    exit 1
  }
else
  echo "[warn] No schedule groups available; skipping schedule creation"
fi

echo "[ui] Reports page + JSON view + modal"
curl -s -b "$JAR" -D /tmp/reports_hdrs.txt -o /tmp/reports.html http://localhost/reports >/dev/null
head -n1 /tmp/reports_hdrs.txt | grep -q " 200 " || { echo "[fail] /reports not 200" >&2; exit 1; }
REPORTS_JSON=$(curl -sf -b "$JAR" -H 'X-Test-Json: 1' http://localhost/reports)
REPORT_ID=$(printf "%s" "$REPORTS_JSON" | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1)
if [ -n "$REPORT_ID" ]; then
  curl -sf -b "$JAR" http://localhost/reports/$REPORT_ID/view | grep -q '<div' || {
    echo "[fail] Report modal did not render HTML" >&2
    exit 1
  }
else
  echo "[warn] No reports yet; skipping modal view"
fi

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
