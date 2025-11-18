# Production Deployment Guide

This guide covers production deployment using Docker Compose or Podman, managing services with systemd, setting up Nginx, and building releases.

## Prerequisites

- Linux server with Docker (or Podman) installed
- Domain/DNS (optional but recommended)
- SSL certificates (place into the Nginx volume as noted below)

## 1. Environment Configuration

1. Copy `.env.production.template` to `.env` in the repository root.
2. Set production values:
   - `DB_URL`: Database URL (PostgreSQL recommended)
   - `SESSION_SECRET_KEY`, `API_KEY_HASH_SALT`: strong random secrets
   - `ALLOWED_ORIGINS`: comma-separated origin list for CORS
   - `DATA_DIR`, `LOGS_DIR`, `ARTIFACTS_DIR`: container paths for persistence
   - Optional `REDIS_URL` for session/rate-limit backends

## 2. Build and Run

### Docker Compose

- Build and validate images: `./deployment/build_and_release.sh`
- Start: `docker compose -f docker-compose.prod.yml up -d`
- Stop: `docker compose -f docker-compose.prod.yml down`

### Podman

- Build: `podman build -f backend/Dockerfile -t localhost/compliancepulse-backend:latest .`
- Start: `podman-compose -f podman-compose.prod.yml up -d`
- Stop: `podman-compose -f podman-compose.prod.yml down`

## 3. Nginx Configuration

- File: `deployment/nginx/compliancepulse.conf`
- Volumes (Compose):
  - SSL: `nginx_ssl` mounted at `/etc/nginx/ssl` (provide `fullchain.pem`, `privkey.pem`)
  - Logs: `cp_logs` mounted at `/var/log/nginx`
- Behavior:
  - Proxies `/api/` to the `api:8000` backend
  - Proxies `/static/` to the API's static handler (no static volumes required)
  - Security headers, HTTP/2, TLS settings, and simple rate limiting

## 4. systemd Units

- Units are in `deployment/systemd/` and auto-detect `docker` or `podman`.
- Copy the repository to `/opt/compliancepulse` on the server.
- Install and enable:
  ```bash
  sudo cp -a deployment/systemd/*.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now compliancepulse-api.service
  sudo systemctl enable --now compliancepulse-worker.service
  sudo systemctl enable --now compliancepulse-scheduler.service
  sudo systemctl enable --now compliancepulse-nginx.service
  ```
- Each unit uses security-friendly systemd settings (NoNewPrivileges, ProtectSystem, PrivateTmp, etc.).

## 5. Releases and Registry

- Define `REGISTRY` (e.g., `ghcr.io/your-org`) and `IMAGE_REPO` (default `compliancepulse-backend`).
- Run `deployment/build_and_release.sh` to build and tag images as `VERSION` (file) or code version.
- If `REGISTRY` is set, images are pushed after build.

## 6. Health and Observability

- API health: `GET /health`
- Nginx exposes `/health` endpoint for container health checks
- Logs are available via `docker compose logs` or `journalctl -u compliancepulse-*.service`

## 7. Hardening Tips

- Use PostgreSQL in production and manage credentials securely
- Rotate `SESSION_SECRET_KEY` and `API_KEY_HASH_SALT` as needed
- Pin `ALLOWED_COMMANDS` to the minimal set your rules require
- Set `SESSION_SECURE_COOKIE=true` and restrict CORS origins

