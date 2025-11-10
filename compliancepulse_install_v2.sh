#!/usr/bin/env bash
# ============================================================
# CompliancePulse Phase 0.1 Installer for Rocky Linux
# Improved: auto-cleanup, rebuild, health verification
# ============================================================

set -euo pipefail

# === Color Setup ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# === Logging ===
LOG_FILE="/var/log/compliancepulse-install.log"
mkdir -p "$(dirname "$LOG_FILE")"
exec 1> >(tee -a "$LOG_FILE") 2>&1
echo -e "${CYAN}Installation log: $LOG_FILE${NC}"

# === Cleanup Trap ===
cleanup_on_error() {
    echo -e "${RED}✗ Installation failed. Cleaning up...${NC}"
    cd /opt/compliancepulse 2>/dev/null || true
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    docker system prune -af >/dev/null 2>&1 || true
    echo -e "${YELLOW}Check $LOG_FILE for details.${NC}"
}
trap cleanup_on_error ERR

# === Prerequisites ===
check_prerequisites() {
    echo ">>> [0/11] Checking prerequisites..."
    if [ "$EUID" -eq 0 ]; then
        echo -e "${RED}Error: Do not run as root. Use a sudo-capable user.${NC}"
        exit 1
    fi
    if [ ! -f /etc/rocky-release ]; then
        echo -e "${YELLOW}Warning: Non-Rocky system detected. Continue? (y/n)${NC}"
        read -r ans; [[ "$ans" != "y" ]] && exit 1
    fi
    
    # Check available disk space (need at least 5GB)
    available=$(df /opt 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
    if [ "$available" -lt 5000000 ]; then
        echo -e "${YELLOW}Warning: Less than 5GB available in /opt${NC}"
    fi
    
    echo -e "${GREEN}✓ Prerequisite check complete${NC}"
}
check_prerequisites

# === System Updates & Base Packages ===
echo ">>> [1/11] Updating system..."
sudo dnf -y update

echo ">>> [2/11] Installing core packages..."
sudo dnf -y install git curl wget vim unzip tar net-tools firewalld python3 python3-pip dnf-plugins-core

echo ">>> [3/11] Enabling firewalld..."
sudo systemctl enable --now firewalld

# === Docker Setup ===
echo ">>> [4/11] Installing Docker..."
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker

# Add user to docker group
if ! groups $USER | grep -q '\bdocker\b'; then
    sudo usermod -aG docker $USER
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠  Added $USER to docker group${NC}"
    echo -e "${YELLOW}   Run: newgrp docker (then re-run this script)${NC}"
    echo -e "${YELLOW}   Or logout/login for changes to take effect${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    echo -e "${GREEN}✓ Docker group confirmed${NC}"
fi

# === Directory Setup ===
echo ">>> [5/11] Preparing directories..."
sudo mkdir -p /opt/{codex_env,compliancepulse}
sudo chown -R $USER:$USER /opt/{codex_env,compliancepulse}

# === Codex Environment ===
# === Codex Environment ===
echo ">>> [6/11] Setting up Codex environment..."
cd /opt/codex_env
python3 -m venv venv
( source venv/bin/activate && pip install --upgrade pip setuptools wheel openai requests tqdm pandas )
echo -e "${GREEN}✓ Codex environment ready${NC}"

# === CompliancePulse Setup ===
echo ">>> [7/11] Setting up CompliancePulse scaffold..."
cd /opt/compliancepulse

# Clean any previous failed attempts
docker compose down --remove-orphans >/dev/null 2>&1 || true
docker system prune -af >/dev/null 2>&1 || true
rm -rf backend frontend agent data logs .env || true
mkdir -p backend frontend agent data logs

# === .gitignore ===
cat <<'EOF' > .gitignore
__pycache__/
*.pyc
venv/
.env
node_modules/
.next/
*.log
*.db
data/
logs/
EOF

# === Backend (FastAPI) ===
cat <<'EOF' > backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine, Session, select
import os
from datetime import datetime

app = FastAPI(
    title="CompliancePulse API",
    version="0.1.0",
    description="Compliance monitoring and scanning API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv("DB_URL", "sqlite:////app/data/compliancepulse.db")
engine = create_engine(DB_URL, echo=True)

class System(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hostname: str = Field(index=True)
    ip: str | None = None
    os_version: str | None = None
    last_scan: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    system_id: int = Field(foreign_key="system.id")
    score: int = Field(ge=0, le=100)
    issues_json: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class ScanRequest(BaseModel):
    hostname: str
    ip: str | None = None

class ScanResponse(BaseModel):
    hostname: str
    score: int
    issues: list[str]
    scan_time: str

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
    print("✓ Database initialized")

@app.get("/")
def root():
    return {"service": "CompliancePulse API", "version": "0.1.0", "status": "running"}

@app.get("/health")
def health():
    try:
        with Session(engine) as s:
            s.exec(select(System).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")

@app.get("/systems")
def get_systems():
    with Session(engine) as s:
        systems = s.exec(select(System)).all()
        return {"systems": systems, "count": len(systems)}

@app.get("/systems/{system_id}")
def get_system(system_id: int):
    with Session(engine) as s:
        system = s.get(System, system_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")
        return system

@app.post("/scan", response_model=ScanResponse)
def scan_system(request: ScanRequest):
    scan_result = {
        "hostname": request.hostname,
        "score": 87,
        "issues": [
            "Password policy does not meet CIS standards",
            "Firewall not configured properly",
            "SSH root login enabled",
            "No automatic security updates configured"
        ],
        "scan_time": datetime.now().isoformat()
    }
    
    with Session(engine) as s:
        existing = s.exec(select(System).where(System.hostname == request.hostname)).first()
        
        if existing:
            system = existing
            system.last_scan = scan_result["scan_time"]
        else:
            system = System(
                hostname=request.hostname,
                ip=request.ip,
                last_scan=scan_result["scan_time"]
            )
            s.add(system)
        
        s.commit()
        s.refresh(system)
        
        import json
        report = Report(
            system_id=system.id,
            score=scan_result["score"],
            issues_json=json.dumps(scan_result["issues"]),
            created_at=scan_result["scan_time"]
        )
        s.add(report)
        s.commit()
    
    return scan_result

@app.get("/reports")
def get_reports(limit: int = 10):
    with Session(engine) as s:
        reports = s.exec(select(Report).limit(limit)).all()
        return {"reports": reports, "count": len(reports)}
EOF

cat <<'EOF' > backend/requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlmodel==0.0.14
paramiko==3.4.0
pydantic==2.5.0
reportlab==4.0.7
python-dotenv==1.0.0
EOF

cat <<'EOF' > backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# === Frontend ===
cat <<'EOF' > frontend/index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CompliancePulse Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .status-card {
            padding: 25px;
            border-radius: 12px;
            background: #f8f9fa;
            transition: transform 0.2s;
        }
        .status-card:hover {
            transform: translateY(-2px);
        }
        .status-card h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .status-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .status-card.loading .value { color: #999; }
        .status-card.healthy .value { color: #28a745; }
        .status-card.error .value { color: #dc3545; }
        
        .actions {
            margin-bottom: 30px;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            margin-right: 10px;
        }
        button:hover {
            background: #5568d3;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .systems {
            margin-top: 30px;
        }
        .systems h2 {
            color: #667eea;
            margin-bottom: 15px;
        }
        .system-item {
            padding: 20px;
            background: #f8f9fa;
            margin-bottom: 10px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
        }
        .system-item:hover {
            background: #e9ecef;
        }
        .system-info strong {
            display: block;
            color: #333;
            font-size: 1.1em;
            margin-bottom: 5px;
        }
        .system-info small {
            color: #666;
        }
        .system-score {
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #f0f0f0;
            text-align: center;
            color: #999;
            font-size: 0.9em;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ CompliancePulse</h1>
        <p class="subtitle">Security Compliance Monitoring Dashboard</p>
        
        <div class="status-grid">
            <div class="status-card loading" id="backend-status">
                <h3>Backend Status</h3>
                <div class="value">Checking...</div>
            </div>
            <div class="status-card loading" id="systems-count">
                <h3>Monitored Systems</h3>
                <div class="value">—</div>
            </div>
            <div class="status-card loading" id="avg-score">
                <h3>Average Score</h3>
                <div class="value">—</div>
            </div>
        </div>
        
        <div class="actions">
            <button onclick="testScan()" id="scan-btn">🔍 Run Test Scan</button>
            <button onclick="loadSystems()">🔄 Refresh</button>
        </div>
        
        <div class="systems" id="systems-container">
            <h2>Recent Scans</h2>
            <div id="systems-list" class="empty-state">
                <p>No systems scanned yet. Click "Run Test Scan" to get started!</p>
            </div>
        </div>
        
        <div class="footer">
            CompliancePulse Phase 0.1 | Backend: <span id="api-url">—</span>
        </div>
    </div>
    
    <script>
        const API_URL = 'http://' + window.location.hostname + ':8000';
        document.getElementById('api-url').textContent = API_URL;
        
        async function checkBackend() {
            try {
                const response = await fetch(`${API_URL}/health`);
                const data = await response.json();
                const statusCard = document.getElementById('backend-status');
                statusCard.className = 'status-card healthy';
                statusCard.querySelector('.value').textContent = '✓ Healthy';
                return true;
            } catch (error) {
                const statusCard = document.getElementById('backend-status');
                statusCard.className = 'status-card error';
                statusCard.querySelector('.value').textContent = '✗ Offline';
                return false;
            }
        }
        
        async function loadSystems() {
            try {
                const response = await fetch(`${API_URL}/systems`);
                const data = await response.json();
                
                const countCard = document.getElementById('systems-count');
                countCard.className = 'status-card';
                countCard.querySelector('.value').textContent = data.count || 0;
                
                const systemsList = document.getElementById('systems-list');
                if (data.systems && data.systems.length > 0) {
                    systemsList.className = '';
                    systemsList.innerHTML = data.systems.map(s => `
                        <div class="system-item">
                            <div class="system-info">
                                <strong>${s.hostname}</strong>
                                <small>${s.ip || 'No IP'} • Last scan: ${s.last_scan ? new Date(s.last_scan).toLocaleString() : 'Never'}</small>
                            </div>
                            <div class="system-score">87/100</div>
                        </div>
                    `).join('');
                } else {
                    systemsList.className = 'empty-state';
                    systemsList.innerHTML = '<p>No systems scanned yet. Click "Run Test Scan" to get started!</p>';
                }
            } catch (error) {
                console.error('Failed to load systems:', error);
            }
        }
        
        async function testScan() {
            const btn = document.getElementById('scan-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Scanning...';
            
            try {
                const response = await fetch(`${API_URL}/scan`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        hostname: 'server-' + Date.now(),
                        ip: '192.168.1.' + Math.floor(Math.random() * 255)
                    })
                });
                const data = await response.json();
                alert(`✅ Scan Complete!\n\nScore: ${data.score}/100\nIssues Found: ${data.issues.length}\n\nIssues:\n${data.issues.map(i => '• ' + i).join('\n')}`);
                loadSystems();
            } catch (error) {
                alert('❌ Scan failed: ' + error.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '🔍 Run Test Scan';
            }
        }
        
        // Initialize
        checkBackend();
        loadSystems();
        
        // Auto-refresh every 10 seconds
        setInterval(() => {
            checkBackend();
            loadSystems();
        }, 10000);
    </script>
</body>
</html>
EOF

cat <<'EOF' > frontend/Dockerfile
FROM node:18-slim

WORKDIR /app

RUN npm install -g serve

COPY . .

EXPOSE 3000

CMD ["serve", "-s", ".", "-l", "3000"]
EOF

# === Agent ===
cat <<'EOF' > agent/scan_agent.py
#!/usr/bin/env python3
"""
CompliancePulse Scanning Agent
Phase 0.1: Mock implementation
"""
import json
import sys
from datetime import datetime

def scan_system(hostname, ip=None):
    """Mock system scan - will be replaced with real scanning logic"""
    return {
        "hostname": hostname,
        "ip": ip,
        "score": 87,
        "issues": [
            "Password policy does not meet CIS standards",
            "Firewall not configured properly",
            "SSH root login enabled",
            "No automatic security updates configured"
        ],
        "scan_time": datetime.now().isoformat(),
        "checks_performed": [
            "password_policy",
            "firewall_status",
            "ssh_configuration",
            "update_status"
        ]
    }

if __name__ == "__main__":
    hostname = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    ip = sys.argv[2] if len(sys.argv) > 2 else None
    result = scan_system(hostname, ip)
    print(json.dumps(result, indent=2))
EOF

chmod +x agent/scan_agent.py

# === Docker Compose ===
cat <<'EOF' > docker-compose.yml
services:
  backend:
    build: ./backend
    container_name: compliancepulse-backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DB_URL=sqlite:////app/data/compliancepulse.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s

  frontend:
    build: ./frontend
    container_name: compliancepulse-frontend
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
EOF

# === Environment Files ===
cat <<'EOF' > .env.example
# CompliancePulse Configuration
API_URL=http://localhost:8000
DB_URL=sqlite:////app/data/compliancepulse.db
LOG_LEVEL=INFO
EOF

cp .env.example .env
echo -e "${GREEN}✓ Environment configured${NC}"

# === README ===
cat <<'EOF' > README.md
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
EOF

echo -e "${GREEN}✓ Project files created${NC}"

# === Build + Run Stack ===
echo ">>> [8/11] Building Docker images..."
docker compose build --no-cache

echo ">>> [9/11] Starting containers..."
docker compose up -d

# === Health Check ===
echo ">>> [10/11] Verifying services..."
echo -n "Waiting for backend"
max_attempts=30
attempt=0
backend_healthy=false

while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        backend_healthy=true
        echo ""
        echo -e "${GREEN}✓ Backend is healthy${NC}"
        break
    fi
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
done

if [ "$backend_healthy" = false ]; then
    echo ""
    echo -e "${RED}✗ Backend failed to start${NC}"
    echo "Last 20 log lines:"
    docker compose logs backend | tail -n 20
    exit 1
fi

# Frontend check
sleep 3
if curl -sf http://localhost:3000 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend is running${NC}"
else
    echo -e "${YELLOW}⚠ Frontend may still be starting (give it a moment)${NC}"
fi

# === Firewall ===
echo ">>> [11/11] Configuring firewall..."
sudo firewall-cmd --permanent --add-port=8000/tcp >/dev/null 2>&1
sudo firewall-cmd --permanent --add-port=3000/tcp >/dev/null 2>&1
sudo firewall-cmd --reload >/dev/null 2>&1
echo -e "${GREEN}✓ Firewall configured${NC}"

# === Success Summary ===
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ CompliancePulse Phase 0.1 Installation Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${CYAN}Access Your Installation:${NC}"
echo "  🌐 Dashboard  : http://${SERVER_IP}:3000"
echo "  🔧 Backend API: http://${SERVER_IP}:8000"
echo "  📚 API Docs   : http://${SERVER_IP}:8000/docs"
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo "  docker compose logs -f           # View live logs"
echo "  docker compose ps                # Check service status"
echo "  docker compose restart           # Restart services"
echo "  docker compose down              # Stop all services"
echo "  docker compose up -d --build     # Rebuild & restart"
echo ""
echo -e "${CYAN}Data Locations:${NC}"
echo "  📁 Database  : /opt/compliancepulse/data/"
echo "  📋 Logs      : /opt/compliancepulse/logs/"
echo "  📝 Install   : $LOG_FILE"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Open http://${SERVER_IP}:3000 in your browser"
echo "  2. Click 'Run Test Scan' to test the system"
echo "  3. Check the README.md for more information"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
