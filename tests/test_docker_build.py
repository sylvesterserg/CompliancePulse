import shutil
import subprocess
from pathlib import Path

import pytest


def test_backend_dockerfile_structure():
    dockerfile = Path("backend/Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.11-slim" in dockerfile
    assert "pip install" in dockerfile
    assert "uvicorn" in dockerfile


def test_frontend_dockerfile_uses_node_builder():
    dockerfile = Path("frontend/Dockerfile").read_text(encoding="utf-8")
    assert "FROM node:18-slim" in dockerfile
    assert "serve" in dockerfile


@pytest.mark.slow
def test_docker_build_smoke(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("docker is not available in this environment")
    # Skip if Docker daemon is not reachable
    try:
        info = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if info.returncode != 0:
            pytest.skip("docker daemon is not running")
    except Exception:
        pytest.skip("docker daemon is not running")
    build = subprocess.run(
        ["docker", "build", "-t", "compliancepulse-test", "backend"],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert build.returncode == 0
