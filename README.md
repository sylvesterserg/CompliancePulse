# CompliancePulse

Security compliance monitoring and scanning platform for Rocky Linux systems.

Version: 0.6.0

This repository contains a FastAPI backend with an HTMX/Tailwind-powered UI, a simple scanning agent for demo/dev, and worker/scheduler services for executing and scheduling compliance scans. Multi‑tenant isolation and API keys are built in. Docs and diagrams live under `docs/`.

**Overview**
- Multi-tenant compliance scanning with benchmark-driven rules (YAML)
- FastAPI backend with JSON + HTML responses (UI routes provide JSON fallbacks for tests/automation)
- Worker + Scheduler for asynchronous, rate-limited execution
- SQLite by default; paths configurable via environment
- Secure session middleware, CSRF, API keys, rate limiting, audit logs

**Features**
- Benchmarks: load/validate YAML benchmarks into SQLModel
- Scans: run rules via a guarded shell rule engine; persist artifacts
- Reports: compute weighted compliance scores and summaries
- Scheduling: rule groups + schedules + queueing via jobs
- Security: API keys, rate limiting, audit log, command allow-list
- UI: dashboard, rules, scans, reports with HTMX interactions

**Architecture Summary**
- Backend (FastAPI, SQLModel) under `backend/app`
- Engine (rule engine, executor, scheduler) under `backend/engine`
- Frontend templates + static assets under `frontend/`
- Worker `backend/worker.py` and scheduler `backend/engine/jobs.py`
- Tests in `tests/` and `backend/tests/`

See `docs/architecture.md` and diagrams under `docs/diagrams/`.

**Folder Structure**
- `backend/app`: API, models, schemas, services, security, config
- `backend/engine`: rule engine, executor, scheduler loop
- `frontend`: Jinja2 templates and static assets (HTMX, Tailwind)
- `agent`: example scanning agent
- `tests`, `backend/tests`: pytest suites
- `deploy`: systemd unit files

**Technology Stack**
- Python 3.11, FastAPI, Starlette, SQLModel/SQLAlchemy
- SQLite (default), optional Redis for rate limiting
- Tailwind CSS, HTMX, Jinja2 templates
- Docker Compose / Podman

**How To Run**
- Local (Python)
  - `cd backend && pip install -r requirements.txt`
  - `npm install && npm run build:css` (compile Tailwind to `frontend/static/css/app.css`)
  - `cd backend && uvicorn app.main:app --reload`
  - Open `http://localhost:8000`
- Docker (Compose)
  - `docker compose --profile assets run --rm tailwind` (one-time CSS build)
  - `docker compose up -d --build`
  - Logs: `docker compose logs -f api`
  - Stop: `docker compose down`
- Production (Podman example)
  - Build: `podman build -t compliancepulse -f backend/Dockerfile .`
  - Run: `podman run -d -p 8000:8000 -e DB_URL=sqlite:////app/data/compliancepulse.db -e ENVIRONMENT=production -v ./data:/app/data:Z -v ./logs:/app/logs:Z compliancepulse`
  - For SELinux: `chcon -Rt svirt_sandbox_file_t ./data ./logs ./frontend`

Environment variables (see `docker-compose.yml`):
- `DB_URL`, `ENVIRONMENT`, `SESSION_SECRET_KEY`, `API_KEY_HASH_SALT`, `STRIPE_WEBHOOK_SECRET`
- `ALLOWED_COMMANDS`, `MAX_SCAN_RUNTIME_PER_JOB`, `MAX_CONCURRENT_JOBS_PER_ORG`
- `API_KEY_RATE_LIMIT`, `API_KEY_RATE_WINDOW_SECONDS`, `AUDIT_LOG_RETENTION_DAYS`, `SECURITY_TEST_MODE`

**Testing Instructions**
- Install dev deps as above
- Run tests: `pytest -q`
- Useful markers: `-m integration`, `-m worker`, `-m smoke`, `-m slow`, `-m acl`
- See `docs/tests.md` for fixtures, ASGI test client, and tips

**Developer Workflows**
- API/UI changes: update `backend/app/api/*` and templates, run `npm run build:css`
- Benchmarks: edit YAML files under `backend/benchmarks/`, then `POST /benchmarks/reload`
- Background jobs: run `python backend/worker.py` and `python backend/scheduler_service.py`
- Security settings: tune via env, see section below and `backend/app/security/*`

**CLI Commands**
- API (dev): `uvicorn app.main:app --reload`
- Worker: `python backend/worker.py`
- Scheduler: `python backend/scheduler_service.py`
- Agent: `python agent/scan_agent.py <hostname> [ip]`
- Tailwind: `npm run build:css`

**Versioning**
- Semantic Versioning (SemVer). Current API version: `0.6.0` (see `backend/app/config.py`).
- Release notes for the next `0.7.0` are in `RELEASE_NOTES_v0.7.0.md`.

**Future Roadmap**
- PostgreSQL support + migrations
- Real remote agent with secure transport and attestation
- Web UI enhancements: live scan streaming, advanced filters
- RBAC improvements and audit log export
- S3-compatible artifact storage, signed URLs
- OpenAPI examples + client SDKs

**Security + Observability**
- Middleware: request logging with IP/latency, JSON body mirroring in test mode, cookie-based sessions
- Audit log events on scans, scheduler, worker failures
- Rate limiting (memory; Redis-ready) and API key management
- Command allowlist for shell execution (`ALLOWED_COMMANDS`)

**API Keys**
- `GET /settings/api-keys` – list
- `POST /settings/api-keys/create` – create (returns plaintext once)
- `GET /settings/api-keys/{id}/show` – show
- `POST /settings/api-keys/{id}/revoke` – revoke
Auth via `Authorization: Bearer <token>` or `X-API-Key`.

**Diagrams & Docs**
- Architecture, services, data flow, and API routing diagrams in `docs/diagrams/`
- Developer docs under `docs/`

For a full API list and usage, see `docs/api.md`.

### Auth & Smoke Tests

- UI forms post to `/api/auth/login` and `/api/auth/register` (proxied to backend `/auth/*`).
- CSRF is injected into templates; HTMX requests include `X-CSRF-Token` where applicable.
- In production behind TLS, set `SESSION_SECURE_COOKIE=true`; cookie secure flag is auto-disabled on plain HTTP using `X-Forwarded-Proto`.

Run the end-to-end smoke test:

```
bash ./deployment/stack_smoke.sh
```

This validates NGINX, API health, UI login + cookie, dashboard HTML, static assets, Rules/Scans/Schedules/Reports UI flows, and tail logs for stability.

## Production Deployment (Phase 1.0)

This section explains production deployment with Docker Compose or Podman, systemd units, Nginx, environment variables, and release builds.

- Configure environment: copy `.env.production.template` to `.env` and set values
  - `DB_URL` (database), `SESSION_SECRET_KEY`, `API_KEY_HASH_SALT` (secrets)
  - Rate limits and directories (`DATA_DIR`, `LOGS_DIR`, `ARTIFACTS_DIR`)
  - `ALLOWED_ORIGINS` for CORS

- Docker Compose
  - Build/validate: `./deployment/build_and_release.sh`
  - Start: `docker compose -f docker-compose.prod.yml up -d`
  - Stop: `docker compose -f docker-compose.prod.yml down`

- Podman
  - Build: `podman build -f backend/Dockerfile -t localhost/compliancepulse-backend:latest .`
  - Start: `podman-compose -f podman-compose.prod.yml up -d`

- Nginx
  - Config at `deployment/nginx/compliancepulse.conf`
  - Provide SSL certs in the `nginx_ssl` volume (`/etc/nginx/ssl`)
  - Proxies `/api/` and `/` to backend; forwards `/static/` to the API static endpoint

- systemd Units
  - Copy repo to `/opt/compliancepulse` on the server
  - Install: `sudo cp -a deployment/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload`
  - Enable: `sudo systemctl enable --now compliancepulse-api.service compliancepulse-worker.service compliancepulse-scheduler.service compliancepulse-nginx.service`

- Releases
  - Optional push: set `REGISTRY` (e.g., `ghcr.io/your-org`) and run `deployment/build_and_release.sh`
  - Script tags images with `VERSION` file or code version and validates compose
