import asyncio
import uuid


def test_rules_listing_behaves_like_htmx_partial(async_client):
    response = asyncio.run(async_client.get("/rules", headers={"HX-Request": "true"}))
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert all(rule["id"] for rule in payload)


def test_post_scans_trigger_returns_updated_table(async_client):
    hostname = f"modal-host-{uuid.uuid4().hex[:8]}"
    response = asyncio.run(
        async_client.post(
            "/scans",
            headers={"HX-Request": "true"},
            json={
                "hostname": hostname,
                "ip": "198.51.100.23",
                "benchmark_id": "rocky_l1_foundation",
            },
        )
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["hostname"] == hostname
    assert detail["results"], "expected rule execution results for HTMX refresh"


def test_get_scans_refreshes_htmx_table(async_client, completed_scan):
    response = asyncio.run(async_client.get("/scans", headers={"HX-Request": "true"}))
    assert response.status_code == 200
    rows = response.json()
    assert any(row["id"] == completed_scan["id"] for row in rows)


def test_report_view_modal_returns_detail(async_client, completed_scan):
    report_listing = asyncio.run(async_client.get("/reports"))
    report_listing.raise_for_status()
    report_id = report_listing.json()[0]["id"]
    response = asyncio.run(
        async_client.get(f"/reports/{report_id}", headers={"HX-Request": "true"})
    )
    assert response.status_code == 200
    report = response.json()
    assert report["id"] == report_id
    assert "summary" in report
