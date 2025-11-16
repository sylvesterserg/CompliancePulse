# CompliancePulse

Security compliance monitoring and scanning platform for Rocky Linux systems.

## Quick Start

```bash
# Compile Tailwind assets once (optional in dev)
docker compose --profile assets run --rm tailwind

# Start services
docker compose up -d --build

# View logs
docker compose logs -f api

# Stop services
docker compose down
```

## Access Points

- **Dashboard + API**: http://localhost:8000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Development

```bash
# Install Python deps
cd backend && pip install -r requirements.txt

# Run Tailwind build locally
npm install
npm run build:css

# Launch API with auto reload
cd backend && uvicorn app.main:app --reload

# Run agent locally
cd agent
python3 scan_agent.py <hostname> [ip]

# Check service health
curl http://localhost:8000/health
```

## Architecture

- **Backend**: FastAPI + SQLModel (Python 3.11)
- **Frontend**: FastAPI templates + HTMX-lite interactions
- **Database**: SQLite (persistent volume)
- **Agent**: Python scanning script

## Data Persistence

- Database: `./data/compliancepulse.db`
- Logs: `./logs/`

## Tailwind Build Pipeline

1. Update templates or `frontend/static/css/tailwind.css`.
2. Run `npm install` once to pull the toolchain.
3. Compile: `npm run build:css` (outputs `frontend/static/css/app.css`).
4. `docker compose --profile assets run --rm tailwind` mirrors the same workflow in containers.

## Phase 0.4 Highlights

✓ FastAPI-driven UI router with Tailwind layout
✓ HTMX-powered modals for rule creation, scan triggers, and report viewers
✓ Expanded models (tags, severity, statuses, artifact tracking)
✓ Multi-stage Docker build with Tailwind compilation
✓ Rocky Linux-focused deployment guidance

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

# Check firewall
sudo firewall-cmd --list-ports
```

## Support

For issues or questions, check `/var/log/compliancepulse-install.log`

## Rocky Linux Deployment (Podman)

```bash
# Build the multi-stage image
podman build -t compliancepulse -f backend/Dockerfile .

# Run API container with SELinux-aware volumes
podman run -d --name compliancepulse \
  -p 8000:8000 \
  -e DB_URL=sqlite:////app/data/compliancepulse.db \
  -e ENVIRONMENT=production \
  -v ./data:/app/data:Z \
  -v ./logs:/app/logs:Z \
  compliancepulse

# Optional Tailwind build inside Podman Compose
podman-compose --profile assets run --rm tailwind
podman-compose up -d

# SELinux tips
sudo chcon -Rt svirt_sandbox_file_t ./data ./logs ./frontend
```
