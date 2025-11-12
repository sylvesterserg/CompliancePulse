# CompliancePulse

Security compliance monitoring and scanning platform for Linux systems.

## Quick Start

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

## Access Points

- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Development

```bash
# Rebuild after code changes
docker compose up -d --build

# Run agent locally
cd agent
python3 scan_agent.py <hostname> [ip]

# View backend logs
docker compose logs -f backend

# Check service health
curl http://localhost:8000/health
```

### Security & Linting

- Frontend assets are lint-friendly (ESLint) vanilla JavaScript and CSS files located in `frontend/app.js` and `frontend/styles.css`.
- The dashboard now enforces a strict Content Security Policy and never injects unsanitized HTML, protecting against XSS per the OWASP ASVS requirements.
- Backend CORS rules default to `http://localhost:3000`, `http://127.0.0.1:3000`, and `http://0.0.0.0:3000`. Override the comma-separated list via the `FRONTEND_ORIGINS` environment variable.
- Database echo logging is disabled by default. Set `SQL_ECHO=true` locally when you need verbose SQL debugging.

## Architecture

- **Backend**: FastAPI + SQLModel (Python 3.11)
- **Frontend**: Static HTML + Vanilla JS
- **Database**: SQLite (persistent volume)
- **Agent**: Python scanning script

## Data Persistence

- Database: `./data/compliancepulse.db`
- Logs: `./logs/`

## Phase 0.1 Features

✓ FastAPI backend with health checks  
✓ Interactive web dashboard  
✓ Mock scanning agent  
✓ Data persistence with volumes  
✓ CORS support  
✓ System and report tracking  

## Roadmap

**Phase 1**: Real SSH-based scanning, authentication, PostgreSQL  
**Phase 2**: Enhanced dashboard, real-time updates, reporting  
**Phase 3**: Multi-node scanning, compliance frameworks, alerting  

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

## Risk & Rollback Checklist

### Potential Risks

- **Stricter CORS policy** – only configured origins may reach the API. ✅ Confirm `FRONTEND_ORIGINS` includes every required host before deploying.
- **Content Security Policy enforcement** – the dashboard now blocks inline scripts. ✅ Ensure any custom scripts are referenced as external files.
- **Validation tightening** – hostname/IP validation rejects malformed input. ✅ Update any automation that previously submitted non-compliant values.
- **Average score calculations** – dashboards rely on recent reports. ✅ Verify report retention to avoid misleading averages.

### Rollback Plan

1. Revert the deployment to the previous container image or Git commit (`git revert <commit_sha>` or redeploy the prior tag).
2. Restore the earlier static assets by copying back the old `frontend/index.html` if custom branding relied on inline scripts/styles.
3. Reset environment variables if `FRONTEND_ORIGINS` or `SQL_ECHO` were changed for the release.
4. Confirm API health (`curl http://localhost:8000/health`) and dashboard availability after rollback.

## Support

For issues or questions, check `/var/log/compliancepulse-install.log`
