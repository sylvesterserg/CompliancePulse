# CompliancePulse Installation

- Supported OS: Rocky Linux 9 (recommended), Ubuntu 22.04+
- Required ports: 80 (HTTP), 443 (HTTPS if terminated upstream)

## Quick start (production)

1. Ensure Docker and Docker Compose are installed.
2. Run `deployment/install/install_v3.sh` as root.
3. Access the app at `http://<host>/`.

## Environment configuration

Create `.env` in repo root. Important vars:

- `DB_URL`: database URL (SQLite default). For Postgres: `postgresql+psycopg2://user:pass@host/db`.
- `SESSION_SECRET_KEY`: random 32+ char secret
- `APP_VERSION`: display/version API (defaults to version.py)

The installer writes `APP_VERSION=1.0.0-alpha` to `.env` if missing.

## Local development

- `docker compose up -d` (builds backend and serves UI)
- API at `http://localhost:8000`

