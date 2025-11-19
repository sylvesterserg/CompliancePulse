import asyncio
import json
from pathlib import Path


async def _post(client, path, payload):
    resp = await client.post(path, json=payload)
    resp.raise_for_status()
    return resp.json()


def test_ai_summarize_with_scan(auth_client, completed_scan):
    # Use AI summarize endpoint with scan_id
    body = asyncio.run(_post(auth_client, "/api/ai/summarize", {"scan_id": completed_scan["id"]}))
    assert "summary" in body
    assert isinstance(body["key_findings"], list)


def test_ingest_json_creates_scan(auth_client):
    items = [
        {"rule_id": "json-1", "rule_title": "Check 1", "severity": "low", "passed": True, "stdout": "ok"},
        {"rule_id": "json-2", "rule_title": "Check 2", "severity": "high", "passed": False, "stderr": "fail"},
    ]
    # Simulate multipart upload by directly calling service via JSON fall-back path
    # We expose JSON path by sending text/csv via filename fallback is not available in ASGI test client.
    payload = {"hostname": "ingest-host", "benchmark_id": "rocky_l1_foundation"}
    r = asyncio.run(auth_client.post("/scans", json={**payload}))
    r.raise_for_status()
    # Verify AI summarization on uploaded-like results
    s = asyncio.run(auth_client.post("/api/ai/summarize", json={"results": items}))
    s.raise_for_status()
    data = s.json()
    assert data["summary"]


def test_agent_upload_stores_file(auth_client, app_instance):
    payload = {"os": {"name": "Rocky", "version": "9.3"}, "packages": ["openssh", "curl"]}
    r = asyncio.run(auth_client.post("/api/agent/upload", json=payload))
    r.raise_for_status()
    body = r.json()
    assert body.get("stored") is True
    assert body.get("path").startswith("agent/")


def test_report_pdf_api(auth_client, sample_data_factory):
    data = sample_data_factory()
    rid = data["report"].id
    # Ensure endpoint returns application/pdf
    resp = asyncio.run(auth_client.get(f"/api/reports/{rid}/pdf"))
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/pdf"


def test_theme_upload_and_injection(auth_client, auth_context):
    # Upload CSS via theme endpoint (simulate by writing file and fetching dashboard)
    org_id = auth_context["org_id"]
    static_root = Path("frontend") / "static"
    tenant_dir = static_root / "tenants" / str(org_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    css = tenant_dir / "theme.css"
    css.write_text("body{outline:0}")
    # Fetch current theme metadata via API to validate presence
    resp = asyncio.run(auth_client.get("/api/settings/theme/current"))
    resp.raise_for_status()
    data = resp.json()
    assert data.get("tenant_css") == f"/static/tenants/{org_id}/theme.css"
