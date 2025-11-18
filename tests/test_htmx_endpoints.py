import asyncio
import uuid
import pytest


@pytest.mark.acl
def test_auth_required_for_api_endpoints(unauth_client):
    # List endpoints should deny unauthenticated callers
    for path in ["/scans", "/reports", "/rules"]:
        resp = asyncio.run(unauth_client.get(path))
        # UI routes fallback to JSON 401, API routes require auth via dependencies
        assert resp.status_code in (401, 403)


def test_authenticated_scan_lifecycle(auth_client):
    hostname = f"api-host-{uuid.uuid4().hex[:8]}"
    # Create scan
    create = asyncio.run(
        auth_client.post(
            "/scans",
            json={
                "hostname": hostname,
                "ip": "198.51.100.23",
                "benchmark_id": "rocky_l1_foundation",
            },
        )
    )
    assert create.status_code == 200
    detail = create.json()
    assert detail["hostname"] == hostname
    assert detail["results"], "expected rule execution results"
    scan_id = detail["id"]

    # List + get
    listing = asyncio.run(auth_client.get("/scans"))
    assert listing.status_code == 200
    payload = listing.json()
    if isinstance(payload, list):
        assert any(item["id"] == scan_id for item in payload)
    else:
        # UI JSON fallback may return a summary dict without items
        assert isinstance(payload, dict)
        assert "count" in payload

    show = asyncio.run(auth_client.get(f"/scans/{scan_id}"))
    assert show.status_code == 200
    assert show.json()["id"] == scan_id

    # Report
    rep = asyncio.run(auth_client.get(f"/scans/{scan_id}/report"))
    assert rep.status_code == 200
    assert rep.json()["scan_id"] == scan_id
