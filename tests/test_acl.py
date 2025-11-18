import asyncio
import pytest


@pytest.mark.acl
def test_public_endpoints(unauth_client):
    for path in ["/health", "/api/version", "/api/ping"]:
        resp = asyncio.run(unauth_client.get(path))
        assert resp.status_code == 200


@pytest.mark.acl
def test_auth_required_endpoints(unauth_client):
    # API + UI endpoints must require auth
    protected_paths = [
        "/scans",
        "/reports",
        "/rules",
        "/schedules",
        "/settings/api-keys",
        "/",
    ]
    for path in protected_paths:
        resp = asyncio.run(unauth_client.get(path))
        assert resp.status_code in (401, 403)


@pytest.mark.acl
def test_authenticated_access(auth_client):
    for path in ["/scans", "/reports", "/rules"]:
        resp = asyncio.run(auth_client.get(path))
        assert resp.status_code == 200
