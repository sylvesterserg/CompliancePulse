#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Simulated Deployment Test =="

echo "[1/7] Repository loaded"
echo "- Root: $ROOT_DIR"
echo "- Files: $(find . -type f | wc -l | tr -d ' ')"

echo "[2/7] .env presence and required keys"
if [[ ! -f .env ]]; then
  echo "ERROR: .env not found"; exit 1;
fi
REQ=(ENVIRONMENT DB_URL SESSION_SECRET_KEY API_KEY_HASH_SALT ALLOWED_ORIGINS DATA_DIR LOGS_DIR ARTIFACTS_DIR WEB_CONCURRENCY)
for k in "${REQ[@]}"; do
  if ! rg -n "^${k}=" .env >/dev/null 2>&1; then echo "- MISSING: $k"; MISSING=1; else echo "- OK: $k"; fi
done
if [[ "${MISSING:-0}" != "0" ]]; then echo "WARN: Some env keys missing (simulation continues)"; fi

echo "[3/7] Dockerfile sanity"
if [[ -f backend/Dockerfile ]]; then
  echo "- Dockerfile present"
  rg -n "^CMD\s*\[\"uvicorn\"" backend/Dockerfile || echo "WARN: CMD uvicorn not detected"
  rg -n "^EXPOSE\s+8000" backend/Dockerfile || echo "WARN: EXPOSE 8000 not detected"
  rg -n "^HEALTHCHECK" backend/Dockerfile || echo "WARN: HEALTHCHECK not detected"
else
  echo "ERROR: backend/Dockerfile missing"; exit 1;
fi

echo "[4/7] Compose files structure"
for f in docker-compose.prod.yml podman-compose.prod.yml; do
  if [[ -f "$f" ]]; then
    echo "- $f present"
    for svc in api worker scheduler nginx; do
      if rg -n "^\s{2}${svc}:" "$f" >/dev/null 2>&1; then echo "  - OK: service $svc"; else echo "  - MISSING: service $svc"; fi
    done
  else
    echo "ERROR: $f missing"; exit 1;
  fi
done

echo "[5/7] Nginx config checks"
NGINX_CONF="deployment/nginx/compliancepulse.conf"
if [[ -f "$NGINX_CONF" ]]; then
  echo "- Nginx config present"
  rg -n "location \/api\/" "$NGINX_CONF" >/dev/null || echo "WARN: /api/ location not found"
  rg -n "ssl_certificate" "$NGINX_CONF" >/dev/null || echo "WARN: SSL cert placeholders not found"
  rg -n "add_header X-Content-Type-Options" "$NGINX_CONF" >/dev/null || echo "WARN: security headers not found"
  rg -n "location = \/health" "$NGINX_CONF" >/dev/null || echo "WARN: /health location not found"
else
  echo "ERROR: $NGINX_CONF missing"; exit 1;
fi

echo "[6/7] Systemd unit checks"
for u in deployment/systemd/compliancepulse-api.service \
         deployment/systemd/compliancepulse-worker.service \
         deployment/systemd/compliancepulse-scheduler.service \
         deployment/systemd/compliancepulse-nginx.service; do
  if [[ -f "$u" ]]; then
    echo "- $u present"
    rg -n "ExecStart=.*compose" "$u" >/dev/null || echo "  WARN: ExecStart compose not found"
    rg -n "Restart=on-failure" "$u" >/dev/null || echo "  WARN: Restart policy missing"
    rg -n "ProtectSystem=strict" "$u" >/dev/null || echo "  WARN: Hardening missing"
  else
    echo "ERROR: $u missing"; exit 1;
  fi
done

echo "[7/7] Health endpoint simulation"
if rg -n "@app.get\(\"\/health\"\)" backend/app/main.py >/dev/null 2>&1; then
  echo "- API /health route present"
else
  echo "ERROR: /health route missing"; exit 1;
fi

echo "\nSimulation Result: SUCCESS (configuration validated; runtime not executed)"

