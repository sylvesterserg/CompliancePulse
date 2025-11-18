import asyncio
from typing import Dict
import pytest


def fetch_dashboard_snapshot(client) -> Dict[str, object]:
    health = asyncio.run(client.get("/health")).json()
    dashboard = asyncio.run(client.get("/"))
    return {"health": health, "dashboard": dashboard.json()}


@pytest.mark.smoke
def test_dashboard_snapshot_contains_all_widgets(auth_client, completed_scan):
    snapshot = fetch_dashboard_snapshot(auth_client)
    assert snapshot["health"]["status"] == "healthy"
    dash = snapshot["dashboard"]
    assert dash["page"] == "dashboard"
    assert dash["scans_count"] >= 1


def test_dashboard_compliance_score_is_reasonable(auth_client):
    dash = asyncio.run(auth_client.get("/")).json()
    assert 0.0 <= dash.get("compliance_score", 0.0) <= 100.0
