import asyncio


def test_root_route_returns_service_banner(async_client):
    response = asyncio.run(async_client.get("/"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"].startswith("CompliancePulse")
    assert payload["status"] == "running"


def test_rules_route_lists_seeded_rules(async_client):
    response = asyncio.run(async_client.get("/rules"))
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) >= 3
    first_rule = rules[0]
    assert {"id", "title", "severity"}.issubset(first_rule.keys())


def test_scans_route_renders_recent_entries(async_client, completed_scan):
    response = asyncio.run(async_client.get("/scans"))
    assert response.status_code == 200
    scans = response.json()
    assert any(scan["id"] == completed_scan["id"] for scan in scans)
    assert all("status" in scan for scan in scans)


def test_reports_route_includes_generated_report(async_client, completed_scan):
    response = asyncio.run(async_client.get("/reports"))
    assert response.status_code == 200
    reports = response.json()
    assert reports, "Expected at least one generated report"
    assert any(report["scan_id"] == completed_scan["id"] for report in reports)
    assert all("summary" in report for report in reports)
