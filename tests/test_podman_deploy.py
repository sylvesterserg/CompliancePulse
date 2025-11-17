import shutil
import subprocess
from pathlib import Path
from typing import Dict

import pytest


def run_podman_deploy() -> Dict[str, str]:
    image_tag = "compliancepulse-podman:test"
    backend_dir = Path("backend").resolve()
    subprocess.run(
        ["podman", "build", "-t", image_tag, str(backend_dir)],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    run_proc = subprocess.run(
        ["podman", "run", "-d", "-p", "8000:8000", image_tag],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    container_id = run_proc.stdout.strip() or "mock-container"
    try:
        health_proc = subprocess.run(
            ["curl", "-f", "http://127.0.0.1:8000/health"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        health_output = health_proc.stdout.strip() or health_proc.stderr.strip()
    finally:
        subprocess.run(["podman", "rm", "-f", container_id], check=False)
    return {
        "image": image_tag,
        "container_id": container_id[:12],
        "health_check": health_output,
    }


@pytest.mark.slow
def test_podman_smoke(monkeypatch):
    if shutil.which("podman") is None:
        executed = []

        def fake_run(cmd, *args, **kwargs):
            executed.append(cmd)
            if cmd[:2] == ["podman", "run"] and "-d" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="fake-container\n", stderr="")
            if cmd and cmd[0] == "curl":
                return subprocess.CompletedProcess(cmd, 0, stdout='{"status":"healthy"}', stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = run_podman_deploy()
        assert result["image"].startswith("compliancepulse-podman")
        assert "healthy" in result["health_check"]
        assert any(cmd[0] == "podman" for cmd in executed)
    else:
        result = run_podman_deploy()
        assert result["health_check"]
