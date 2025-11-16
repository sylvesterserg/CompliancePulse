# CompliancePulse

Security compliance monitoring and scanning platform for Linux systems. The repository is intentionally split into service-specific folders so you always know where a change belongs.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `agent/` | Standalone Python scanner CLI ([docs](agent/README.md)) |
| `backend/` | FastAPI + SQLModel API ([docs](backend/README.md)) |
| `frontend/` | Static dashboard served over HTTP ([docs](frontend/README.md)) |
| `docker-compose.yml` | Source of truth for how services are orchestrated |
| `compliancepulse_install_v2.sh` | Convenience installer for bare-metal hosts |

## Quick Start (Docker Compose)

```bash
# Build + start services
docker compose up -d --build

# Follow logs
docker compose logs -f

# Stop everything
docker compose down
```

### Access Points
- **Frontend Dashboard** http://localhost:3000
- **Backend API** http://localhost:8000
- **API Docs** http://localhost:8000/docs

## Development Commands

```bash
# Syntax check Python services
make lint

# Validate docker-compose configuration
make test

# Run services individually
make backend
make frontend
make agent
```

The `Makefile` gives contributors one entry point for routine tasks. Extend it as you add formal linting/testing.

## Architecture Snapshot

- **Backend**: FastAPI + SQLModel (Python 3.11) with SQLite storage mounted from `./data`.
- **Frontend**: Static HTML + Vanilla JS fetching backend endpoints.
- **Agent**: Python CLI that simulates scan output for now.
- **Orchestration**: Docker Compose with health checks and persistent volumes.

## Data Persistence & Housekeeping

- Database lives at `./data/compliancepulse.db` (ignored via `.gitignore`).
- Logs emitted by containers live in `./logs/` (also ignored).
- Update `.gitignore` whenever you add new local-only artifacts.

## Roadmap

- **Phase 0.1**: ✅ FastAPI backend, mock agent, dashboard, persistence, health checks.
- **Phase 1**: Real SSH-based scanning, authentication, PostgreSQL.
- **Phase 2**: Enhanced dashboard, real-time updates, reporting.
- **Phase 3**: Multi-node scanning, compliance frameworks, alerting.

## Troubleshooting

```bash
# Check container status
docker compose ps

# View all logs
docker compose logs

# Restart services
docker compose restart

# Clean rebuild
docker compose down && docker compose up -d --build
```

For bare-metal installs, inspect `/var/log/compliancepulse-install.log` from `compliancepulse_install_v2.sh`.
