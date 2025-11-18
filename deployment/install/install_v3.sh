#!/usr/bin/env bash
set -euo pipefail

# CompliancePulse Installer v3 (Rocky Linux)
# - Installs Docker + Compose
# - Configures firewall and NGINX
# - Sets up systemd units for api/worker/scheduler
# - Pulls/builds images and starts the stack

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root" >&2
  exit 1
fi

echo "[1/6] Installing Docker"
dnf -y install dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "[2/6] FirewallD rules (HTTP/HTTPS)"
if systemctl is-active --quiet firewalld; then
  firewall-cmd --add-service=http --permanent || true
  firewall-cmd --add-service=https --permanent || true
  firewall-cmd --reload || true
fi

echo "[3/6] NGINX provided by container; no host nginx required"

echo "[4/6] Pull/build images"
cd "$(dirname "$0")/../.."
docker compose -f docker-compose.prod.yml build

echo "[5/6] Create data/logs directories"
mkdir -p backend/data backend/logs || true

echo "[6/6] Start stack"
docker compose -f docker-compose.prod.yml up -d

echo "Installer complete. Access the app via http://<host>/"
