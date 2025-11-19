#!/usr/bin/env bash
set -euo pipefail

SERVER=""
ORG="1"
AGENT_DIR="/etc/compliancepulse-agent"

usage(){
  echo "Usage: $0 --server <http://host> [--org <id>]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server) SERVER="$2"; shift 2;;
    --org) ORG="$2"; shift 2;;
    *) usage; exit 1;;
  esac
done

if [[ -z "$SERVER" ]]; then
  usage; exit 1
fi

echo "[agent] Installing CompliancePulse agent"
sudo mkdir -p "$AGENT_DIR"
UUID_FILE="$AGENT_DIR/conf.json"

HOSTNAME=$(hostname)
OS=$(uname -s)
VERSION="1.1.0"

echo "[agent] Registering with $SERVER"
TOKEN_RESPONSE=$(curl -sS -X POST "$SERVER/api/agent/register" \
  -H 'content-type: application/json' \
  -d "{\"hostname\":\"$HOSTNAME\",\"os\":\"$OS\",\"version\":\"$VERSION\"}")
TOKEN=$(echo "$TOKEN_RESPONSE" | sed -n 's/.*"token"\s*:\s*"\([^"]*\)".*/\1/p')
UUID=$(echo "$TOKEN_RESPONSE" | sed -n 's/.*"uuid"\s*:\s*"\([^"]*\)".*/\1/p')
if [[ -z "$TOKEN" ]]; then
  echo "[agent] Registration failed: $TOKEN_RESPONSE" >&2
  exit 1
fi

cat << JSON | sudo tee "$UUID_FILE" >/dev/null
{
  "server": "$SERVER",
  "uuid": "$UUID",
  "token": "$TOKEN",
  "version": "$VERSION"
}
JSON

cat << 'UNIT' | sudo tee /etc/systemd/system/compliancepulse-agent.service >/dev/null
[Unit]
Description=CompliancePulse Agent
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m compliancepulse_agent --config /etc/compliancepulse-agent/conf.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now compliancepulse-agent.service
echo "[agent] Installed and started."

