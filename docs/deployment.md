# CompliancePulse Deployment

## NGINX

Containerized NGINX is provided in `docker-compose.prod.yml` and configured via `deployment/nginx/compliancepulse.conf`.

- Routes:
  - `/` → FastAPI UI
  - `/api/` → FastAPI API (preserves request URI)
  - `/static/` → Static assets via backend
  - `/api/health` and `/health` → backend health
- Security:
  - CSP with self/default; inline for simple templates
  - X-Frame-Options SAMEORIGIN, X-Content-Type-Options nosniff
  - Permissions-Policy hardened

## Environment Variables

- `APP_VERSION`: Display and API version
- `SESSION_SECRET_KEY`: HMAC/session secret
- `ALLOWED_ORIGINS`: CORS list, comma-separated
- `FRONTEND_TEMPLATES`, `FRONTEND_STATIC`: override paths

## Postgres

Set `DB_URL=postgresql+psycopg2://user:pass@host:5432/dbname` and ensure psycopg is available in the image or mount it.

## Deployment webhook

Configure a webhook to your VPS/container host:

- Add `DEPLOY_WEBHOOK_URL` and `DEPLOY_WEBHOOK_TOKEN` GitHub secrets
- On pushes to `main` or tags `v*`, the workflow calls POST with JSON `{ ref, service, event }`

