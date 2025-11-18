import asyncio
import pytest


@pytest.mark.acl
def test_ui_routes_unauthenticated_return_json_401(unauth_client):
    for path in ["/", "/rules", "/scans", "/reports"]:
        resp = asyncio.run(unauth_client.get(path))
        assert resp.status_code == 401
        assert resp.json().get("error") == "unauthorized"


@pytest.mark.acl
def test_ui_routes_authenticated_return_json_fallback(auth_client, completed_scan):
    # Request JSON fallbacks and ensure payloads are present
    resp = asyncio.run(auth_client.get("/"))
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("page") == "dashboard"
    assert "rules_count" in data
    assert "scans_count" in data

    for path, key in [
        ("/rules", "count"),
        ("/scans", "count"),
        ("/reports", "count"),
    ]:
        r = asyncio.run(auth_client.get(path))
        assert r.status_code == 200
        payload = r.json()
        if isinstance(payload, dict):
            assert key in payload
        else:
            # Accept list payloads for API-list endpoints
            assert isinstance(payload, list)
