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

## Support

For issues or questions, check `/var/log/compliancepulse-install.log`
