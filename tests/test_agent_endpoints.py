import asyncio
import json


async def _register(client):
    payload = {"hostname": "agent-01", "os": "Linux", "version": "1.1.0"}
    r = await client.post("/api/agent/register", json=payload)
    assert r.status_code == 200
    return r.json()


def test_agent_register_and_auth(unauth_client):
    data = asyncio.run(_register(unauth_client))
    assert data["token"]
    # heartbeat
    hb = asyncio.run(unauth_client.post("/api/agent/heartbeat", json={"version": "1.1.0"}, headers={"authorization": f"Bearer {data['token']}"}))
    assert hb.status_code == 200
    # auth rotate
    ra = asyncio.run(unauth_client.post("/api/agent/auth", json={"uuid": data["uuid"], "hostname": "agent-01"}))
    assert ra.status_code == 200
    assert ra.json()["token"]


def test_agent_job_dispatch_and_result(unauth_client, session):
    # Register
    data = asyncio.run(_register(unauth_client))
    token = data["token"]
    # Create a benchmark and a simple rule
    from backend.app.models import Benchmark, Rule, AgentJob
    b = Benchmark(id="agent_bench", title="Agent Bench", description="", version="1.0", os_target="linux")
    session.add(b)
    session.commit()
    r = Rule(
        id="rb-echo",
        organization_id=1,
        benchmark_id=b.id,
        title="Echo OK",
        description="",
        severity="low",
        remediation="",
        check_type="shell",
        command="echo ok",
        expect_type="equals",
        expect_value="ok",
    )
    session.add(r)
    session.commit()
    # Create a pending job
    job = AgentJob(organization_id=1, agent_id=data["agent_id"], benchmark_id=b.id, rules_json="")
    session.add(job)
    session.commit()
    # Agent polls next job
    nxt = asyncio.run(unauth_client.get("/api/agent/jobs/next", headers={"authorization": f"Bearer {token}"}))
    assert nxt.status_code == 200
    job_payload = nxt.json()
    assert job_payload["id"]
    # Upload result
    upload = {"status": "completed", "results": [{"id": "rb-echo", "passed": True, "stdout": "ok", "severity": "low", "title": "Echo OK"}]}
    done = asyncio.run(unauth_client.post(f"/api/agent/job/{job_payload['id']}/result", json=upload, headers={"authorization": f"Bearer {token}"}))
    assert done.status_code == 200

