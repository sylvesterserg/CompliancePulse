import asyncio
from statistics import mean
from typing import Dict, List


def fetch_dashboard_snapshot(client) -> Dict[str, object]:
    health = asyncio.run(client.get("/health")).json()
    scans = asyncio.run(client.get("/scans")).json()
    reports = asyncio.run(client.get("/reports")).json()
    return {"health": health, "scans": scans, "reports": reports}


def compute_compliance_score(reports: List[Dict[str, object]]) -> float:
    if not reports:
        return 0.0
    return round(mean(report["score"] for report in reports), 2)


def summarize_widget_state(health_payload: Dict[str, object], scans: List[Dict[str, object]]) -> Dict[str, object]:
    failing_scans = [scan for scan in scans if scan.get("status") != "completed"]
    return {
        "health_label": "Healthy" if health_payload.get("status") == "healthy" else "Degraded",
        "failing": failing_scans,
    }


def test_dashboard_snapshot_contains_all_widgets(async_client, completed_scan):
    snapshot = fetch_dashboard_snapshot(async_client)
    assert snapshot["health"]["status"] == "healthy"
    assert any(scan["id"] == completed_scan["id"] for scan in snapshot["scans"])
    assert snapshot["reports"], "reports widget should not be empty"


def test_dashboard_compliance_score_is_consistent(async_client):
    reports = asyncio.run(async_client.get("/reports")).json()
    score = compute_compliance_score(reports)
    assert 0.0 <= score <= 100.0


def test_dashboard_widget_helper_handles_failures():
    scans = [
        {"hostname": "ok-host", "status": "completed"},
        {"hostname": "bad-host", "status": "error"},
    ]
    summary = summarize_widget_state({"status": "healthy"}, scans)
    assert summary["health_label"] == "Healthy"
    assert len(summary["failing"]) == 1
    assert summary["failing"][0]["hostname"] == "bad-host"
