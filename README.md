# CompliancePulse - Universal Compliance Scanner

Universal installer supporting macOS, Linux, and Windows WSL.

## Quick Start

### 1. Run a Compliance Scan
```bash
./scripts/run_scan.sh
```

### 2. Start the API Server
```bash
./scripts/start_api.sh
```

### 3. Configure OpenAI API Key
```bash
./scripts/config.sh set-api-key YOUR_OPENAI_KEY
```

### 4. View Configuration
```bash
./scripts/config.sh show-config
./scripts/config.sh show-token
```

## Directory Structure

```
compliancepulse/
├── backend/          # FastAPI application
├── scripts/          # Utility scripts
├── config/           # Configuration files (.env)
├── data/             # Compliance reports
├── certs/            # TLS certificates
├── logs/             # Log files
└── venv/             # Python virtual environment
```

## API Endpoints

### Health Check (No Auth Required)
```bash
curl http://localhost:8000/health
```

### Get Latest Report
```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://localhost:8000/api/report
```

### Get Report History
```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://localhost:8000/api/reports/history?limit=10
```

## Environment Support

- ✅ macOS (Intel & Apple Silicon)
- ✅ Rocky Linux / RHEL / CentOS
- ✅ Ubuntu / Debian
- ✅ Windows WSL2
- ✅ Development mode (no root required)

## Troubleshooting

### Check Logs
```bash
tail -f logs/scan.log
tail -f logs/api.log
```

### Reset Configuration
```bash
./scripts/config.sh reset-token
```

### Reinstall Python Dependencies
```bash
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Security Notes

- Tokens are stored in `config/.env` (chmod 600)
- Self-signed certificates are used (replace for production)
- Sensitive data is automatically redacted from reports
- API key is never logged

