import asyncio
import uuid


def test_rules_crud_htmx_partials(auth_client):
    rid = f"T-API-HTMX-{uuid.uuid4().hex[:8]}"
    form = {
        "rule_id": rid,
        "benchmark_id": "rocky_l1_foundation",
        "title": "API HTMX Create",
        "severity": "low",
        "tags": "x,y",
        "description": "",
        "remediation": "",
        "command": "echo 1",
        "expect_value": "1",
    }
    headers = {"X-CSRF-Token": "test", "HX-Request": "true", "accept": "text/html"}
    r = asyncio.run(auth_client.post("/api/rules/create", json=form, headers=headers))
    assert r.status_code == 200

    upd = asyncio.run(
        auth_client.post(
            f"/api/rules/{rid}/update",
            data={
                "title": "API HTMX Updated",
                "severity": "medium",
                "tags": "a,b",
                "benchmark_id": "rocky_l1_foundation",
                "command": "echo 2",
                "expect_value": "2",
            },
            headers=headers,
        )
    )
    assert upd.status_code == 200

    dele = asyncio.run(auth_client.post(f"/api/rules/{rid}/delete", headers=headers))
    assert dele.status_code == 200


def test_rules_crud_json(auth_client):
    rid = f"T-API-JSON-{uuid.uuid4().hex[:8]}"
    headers = {"X-CSRF-Token": "test", "content-type": "application/json", "accept": "application/json"}
    payload = {
        "id": rid,
        "rule_id": rid,
        "benchmark_id": "rocky_l1_foundation",
        "title": "API JSON Create",
        "severity": "high",
        "description": "",
        "remediation": "",
        "command": "echo 3",
        "expect_value": "3",
    }
    create = asyncio.run(auth_client.post("/api/rules/create", json=payload, headers=headers))
    assert create.status_code in (200, 201)
    data = create.json()
    assert data["id"] == rid

    update = asyncio.run(
        auth_client.post(
            f"/api/rules/{rid}/update",
            json={"title": "API JSON Updated", "severity": "critical"},
            headers=headers,
        )
    )
    assert update.status_code == 200
    data = update.json()
    assert data["title"].startswith("API JSON")
    assert data["severity"] in ("high", "critical")

    delete = asyncio.run(auth_client.post(f"/api/rules/{rid}/delete", headers=headers))
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True
