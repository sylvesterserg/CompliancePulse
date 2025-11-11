#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="$(dirname "$0")/../venv"
BACKEND_DIR="$(dirname "$0")/../backend"
CONFIG_DIR="$(dirname "$0")/../config"
BASE_DIR="$(dirname "$0")/.."
CERTS_DIR="$BASE_DIR/certs"
LOGS_DIR="$BASE_DIR/logs"

mkdir -p "$LOGS_DIR"

# Load environment
if [ -f "$CONFIG_DIR/.env" ]; then
    set -a
    source "$CONFIG_DIR/.env"
    set +a
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Check if FastAPI/uvicorn is installed
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "FastAPI/uvicorn not installed. Installing..."
    pip install fastapi uvicorn python-multipart
fi

cd "$BACKEND_DIR" || exit 1

echo "Starting CompliancePulse API..."
echo "Base directory: $BASE_DIR"
echo "Logs directory: $LOGS_DIR"
echo ""
echo "API will be available at:"
echo "  http://localhost:8000 (HTTP)"
echo "  https://localhost:8000 (HTTPS - self-signed)"
echo ""

# Run uvicorn with optional SSL
if [ -f "$CERTS_DIR/privkey.pem" ] && [ -f "$CERTS_DIR/fullchain.pem" ]; then
    python3 -m uvicorn main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --ssl-keyfile "$CERTS_DIR/privkey.pem" \
        --ssl-certfile "$CERTS_DIR/fullchain.pem"
else
    echo "Note: SSL certificates not found, running in HTTP mode"
    python3 -m uvicorn main:app \
        --host 0.0.0.0 \
        --port 8000
fi
