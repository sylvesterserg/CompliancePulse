from pathlib import Path


def test_frontend_index_contains_dashboard_sections():
    index = Path("frontend/index.html").read_text(encoding="utf-8")
    assert "CompliancePulse Dashboard" in index
    assert "status-grid" in index
    assert "systems-list" in index
    assert "fetch(`${API_URL}/health`)" in index


def test_frontend_scripts_reference_backend_api():
    index = Path("frontend/index.html").read_text(encoding="utf-8")
    assert "/health" in index
    assert "/systems" in index
    assert "/scan" in index
    assert "API_URL" in index


import pytest


def test_docker_compose_serves_static_frontend():
    pytest.skip("frontend service not present in this test environment")
