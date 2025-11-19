#!/usr/bin/env bash
set -euo pipefail

# Minimal CompliancePulse agent example
# - Collects OS version and a few package names
# - Sends JSON to /api/agent/upload with an API session (cookie) or use API key auth if extended

API_URL="${API_URL:-http://localhost:8000/api/agent/upload}"

OS_NAME=$(uname -s || echo "unknown")
OS_RELEASE=$(uname -r || echo "unknown")
PKGS=()
if command -v rpm >/dev/null 2>&1; then
  PKGS+=( $(rpm -qa | head -n 5) )
elif command -v dpkg >/dev/null 2>&1; then
  PKGS+=( $(dpkg -l | awk '{print $2}' | head -n 5) )
fi

PAYLOAD=$(cat <<JSON
{
  "os": {"name": "${OS_NAME}", "version": "${OS_RELEASE}"},
  "packages": [$(printf '"%s",' "${PKGS[@]}" | sed 's/,$//')]
}
JSON
)

curl -sS -H 'Content-Type: application/json' -d "${PAYLOAD}" "${API_URL}" || {
  echo "Upload failed" >&2
  exit 1
}

echo "OK"

