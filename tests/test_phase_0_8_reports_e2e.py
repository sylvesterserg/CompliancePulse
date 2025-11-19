import asyncio
import json
from pathlib import Path

from sqlmodel import Session


def _make_html_client(app, auth_context):
  # Local helper to get HTML (not JSON fallback)
  from tests.conftest import _ASGITestClient  # type: ignore
  return _ASGITestClient(
      app,
      headers={
          "accept": "text/html",
          "x-test-user": str(auth_context["user_id"]),
          "x-test-org": str(auth_context["org_id"]),
      },
  )


def test_scan_to_report_e2e(auth_client, auth_context):
    # Trigger a scan via JSON API and verify a report is accessible
    payload = {"hostname": "phase08-host", "benchmark_id": "rocky_l1_foundation"}
    resp = asyncio.run(auth_client.post("/scans", json=payload))
    resp.raise_for_status()
    detail = resp.json()
    assert detail["id"] > 0
    # Report for scan exists via API
    report = asyncio.run(auth_client.get(f"/api/scans/{detail['id']}/report")).json()
    assert report["scan_id"] == detail["id"]
    assert 0.0 <= report["score"] <= 100.0


def test_reports_json_html_pdf(app_instance, auth_client, auth_context):
    # Ensure at least one report exists
    listing = asyncio.run(auth_client.get("/api/reports")).json()
    # If listing returns {page,count}, fetch list via scans service path
    count = listing.get("count") if isinstance(listing, dict) else len(listing)
    assert count is not None

    # Create one more to test endpoints deterministically
    r = asyncio.run(auth_client.post("/scans", json={"hostname": "phase08-render", "benchmark_id": "rocky_l1_foundation"}))
    r.raise_for_status()
    scan = r.json()
    report = asyncio.run(auth_client.get(f"/api/scans/{scan['id']}/report")).json()
    rid = report["id"]

    # JSON detail
    detail = asyncio.run(auth_client.get(f"/api/reports/{rid}"))
    assert detail.status_code == 200
    assert detail.json()["id"] == rid

    # HTML detail
    html_client = _make_html_client(app_instance, auth_context)
    page = asyncio.run(html_client.get(f"/reports/{rid}"))
    assert page.status_code == 200
    # Content may be streamed; ensure non-empty HTML by content-length header
    assert int(page.headers.get("content-length", "1")) > 100

    # PDF
    pdf = asyncio.run(auth_client.get(f"/api/reports/{rid}/pdf"))
    assert pdf.status_code == 200
    assert pdf.headers.get("content-type") == "application/pdf"


def test_reports_dashboard_shows_latest(auth_client):
    dash = asyncio.run(auth_client.get("/")).json()
    reports = dash.get("recent_reports", [])
    assert isinstance(reports, list)
    # dashboard JSON now includes recent reports
    assert len(reports) >= 1


def test_scan_with_no_rules_generates_attention_report(auth_client, session: Session, auth_context):
    # Create a valid benchmark with no rules associated
    from backend.app.models import Benchmark
    b = Benchmark(
        id="empty_benchmark",
        title="Empty Benchmark",
        description="No rules for this benchmark",
        version="0.0",
        os_target="test",
    )
    session.add(b)
    session.commit()

    r = asyncio.run(auth_client.post("/scans", json={"hostname": "no-rules-host", "benchmark_id": b.id}))
    r.raise_for_status()
    scan = r.json()
    rep = asyncio.run(auth_client.get(f"/api/scans/{scan['id']}/report"))
    rep.raise_for_status()
    body = rep.json()
    assert body["score"] == 0.0
    # With zero rules, status should be attention (not passed)
    assert body["status"] == "attention"
