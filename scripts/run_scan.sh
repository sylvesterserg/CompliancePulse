#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="$(dirname "$0")/../venv"
BACKEND_DIR="$(dirname "$0")/../backend"
CONFIG_DIR="$(dirname "$0")/../config"
BASE_DIR="$(dirname "$0")/.."
LOGS_DIR="$BASE_DIR/logs"

mkdir -p "$LOGS_DIR"
LOG_FILE="$LOGS_DIR/scan.log"

echo "[$(date)] Starting compliance scan..." | tee -a "$LOG_FILE"

# Load environment
if [ -f "$CONFIG_DIR/.env" ]; then
    set -a
    source "$CONFIG_DIR/.env"
    set +a
fi

# Activate venv and run
cd "$BACKEND_DIR" || exit 1
source "$VENV_DIR/bin/activate"

python3 codex_agent.py

EXIT_CODE=$?
echo "[$(date)] Scan completed with exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
exit $EXIT_CODE
