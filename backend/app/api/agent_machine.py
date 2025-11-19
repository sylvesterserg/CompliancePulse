from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from ..database import get_session as get_db_session
from ..models import Agent, AgentAuthToken, AgentJob, AgentResult, Benchmark, Rule
from ..schemas.agent import (
    AgentAuthRequest,
    AgentAuthResponse,
    AgentHeartbeatRequest,
    AgentJobPayload,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentResultUpload,
)
from ..security.rate_limit import rate_limit

router = APIRouter(prefix="/agent", tags=["agent-machine"])


def _get_agent_by_token(session: Session, token: str) -> Agent:
    if not token:
        raise HTTPException(status_code=401, detail="missing token")
    rec = session.get(AgentAuthToken, token)
    if not rec or rec.revoked or rec.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="invalid token")
    agent = session.get(Agent, rec.agent_id)
    if not agent:
        raise HTTPException(status_code=401, detail="invalid token")
    session.info["organization_id"] = rec.organization_id
    return agent


def _bearer_token(request: Request) -> str:
    authz = request.headers.get("authorization") or ""
    if authz.lower().startswith("bearer "):
        return authz.split(" ", 1)[1]
    return request.headers.get("x-agent-auth", "")


@router.post("/register", dependencies=[Depends(rate_limit("agent:register", 10, 60))])
def agent_register(
    payload: AgentRegisterRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> AgentRegisterResponse:
    # In absence of full multi-tenant onboarding, default to first org
    from ..models import Organization
    org = session.exec(select(Organization).order_by(Organization.id)).first()
    org_id = org.id if org else 1
    session.info["organization_id"] = org_id

    # Upsert agent by uuid or hostname
    agent: Optional[Agent] = None
    if payload.uuid:
        agent = session.exec(select(Agent).where(Agent.uuid == payload.uuid)).first()
    if not agent:
        agent = Agent(
            organization_id=org_id,
            uuid=payload.uuid or secrets.token_hex(16),
            hostname=payload.hostname,
            ip=payload.ip,
            os=payload.os,
            version=payload.version,
            status="online",
            tags_json=json.dumps(payload.tags or []),
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)
    else:
        agent.hostname = payload.hostname
        agent.ip = payload.ip or agent.ip
        agent.os = payload.os or agent.os
        agent.version = payload.version or agent.version
        agent.status = "online"
        agent.last_seen = datetime.utcnow()
        session.add(agent)
        session.commit()

    token_value = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=24)
    token = AgentAuthToken(token=token_value, agent_id=agent.id, organization_id=org_id, expires_at=expires)
    session.add(token)
    session.commit()
    reg = AgentRegisterResponse(agent_id=agent.id, uuid=agent.uuid, token=token_value, expires_at=expires)
    body = {**reg.model_dump(), "expires_at": reg.expires_at.isoformat()}
    return JSONResponse(body, headers={"x-test-json-body": json.dumps(body)})


@router.post("/auth", dependencies=[Depends(rate_limit("agent:auth", 30, 60))])
def agent_auth(
    payload: AgentAuthRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> AgentAuthResponse:
    agent = session.exec(select(Agent).where(Agent.uuid == payload.uuid)).first()
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    agent.hostname = payload.hostname or agent.hostname
    agent.os = payload.os or agent.os
    agent.version = payload.version or agent.version
    agent.last_seen = datetime.utcnow()
    agent.status = "online"
    session.add(agent)
    session.commit()
    token_value = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=24)
    token = AgentAuthToken(token=token_value, agent_id=agent.id, organization_id=agent.organization_id, expires_at=expires)
    session.add(token)
    session.commit()
    auth = AgentAuthResponse(token=token_value, expires_at=expires)
    body = {**auth.model_dump(), "expires_at": auth.expires_at.isoformat()}
    return JSONResponse(body, headers={"x-test-json-body": json.dumps(body)})


@router.post("/heartbeat", dependencies=[Depends(rate_limit("agent:heartbeat", 120, 60))])
def agent_heartbeat(
    request: Request,
    payload: AgentHeartbeatRequest,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    token = _bearer_token(request)
    agent = _get_agent_by_token(session, token)
    agent.last_seen = datetime.utcnow()
    agent.status = "online"
    if payload.ip:
        agent.ip = payload.ip
    if payload.version:
        agent.version = payload.version
    if payload.tags:
        agent.tags_json = json.dumps(payload.tags)
    session.add(agent)
    session.commit()
    # Return job counts summary
    pending = session.exec(select(AgentJob).where(AgentJob.agent_id == agent.id, AgentJob.status == "pending")).all()
    running = session.exec(select(AgentJob).where(AgentJob.agent_id == agent.id, AgentJob.status == "running")).all()
    return {"ok": True, "pending": len(pending), "running": len(running)}


@router.get("/jobs/next", dependencies=[Depends(rate_limit("agent:jobs", 60, 60))])
def agent_next_job(request: Request, session: Session = Depends(get_db_session)) -> JSONResponse:
    token = _bearer_token(request)
    agent = _get_agent_by_token(session, token)
    job = (
        session.exec(select(AgentJob).where(AgentJob.agent_id == agent.id, AgentJob.status == "pending").order_by(AgentJob.created_at))
        .first()
    )
    if not job:
        return JSONResponse({}, status_code=204)
    job.status = "running"
    job.dispatched_at = datetime.utcnow()
    session.add(job)
    session.commit()
    # If rules_json is empty, hydrate from benchmark
    rules: list[dict[str, Any]]
    if job.rules_json:
        try:
            rules = json.loads(job.rules_json)
        except Exception:
            rules = []
    else:
        rules = []
        items = session.exec(select(Rule).where(Rule.benchmark_id == job.benchmark_id)).all()
        for r in items:
            rules.append({
                "id": r.id,
                "title": r.title,
                "severity": r.severity,
                "description": r.description,
                "remediation": r.remediation,
                "type": (json.loads(r.metadata_json or "{}").get("type") or r.check_type or "shell"),
                "command": r.command,
                "expect_type": r.expect_type,
                "expect_value": r.expect_value,
                "timeout": r.timeout_seconds,
            })
        job.rules_json = json.dumps(rules)
        session.add(job)
        session.commit()
    payload = AgentJobPayload(id=job.id, benchmark_id=job.benchmark_id, rules=rules)
    body = payload.model_dump()
    return JSONResponse(body, headers={"x-test-json-body": json.dumps(body)})


@router.post("/job/{job_id}/result", dependencies=[Depends(rate_limit("agent:result", 60, 60))])
def agent_job_result(
    job_id: int,
    payload: AgentResultUpload,
    request: Request,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    token = _bearer_token(request)
    agent = _get_agent_by_token(session, token)
    job = session.get(AgentJob, job_id)
    if not job or job.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="job not found")
    # Persist raw result
    result = AgentResult(
        organization_id=agent.organization_id,
        agent_job_id=job.id,
        raw_json=json.dumps(payload.model_dump()),
        status=payload.status,
        score=float(payload.score or 0.0),
    )
    job.status = "completed" if payload.status == "completed" else "failed"
    job.completed_at = datetime.utcnow()
    session.add(result)
    session.add(job)
    session.commit()

    # Integrate into Scan/Report pipeline directly to avoid rule persistence collisions
    from ..models import Scan, ScanResult as SRModel, Report
    SEVERITY_WEIGHTS = {"info": 1, "low": 1, "medium": 2, "high": 3, "critical": 4}
    items = payload.results
    total = len(items)
    passed = 0
    w_pass = 0
    w_total = 0
    for it in items:
        if it.get("passed"):
            passed += 1
            w_pass += SEVERITY_WEIGHTS.get(str(it.get("severity", "info")).lower(), 1)
        w_total += SEVERITY_WEIGHTS.get(str(it.get("severity", "info")).lower(), 1)
    score = round((w_pass / w_total) * 100, 2) if w_total else float(payload.score or 0.0)

    scan = Scan(
        organization_id=agent.organization_id,
        hostname=agent.hostname,
        ip=agent.ip,
        benchmark_id=job.benchmark_id,
        group_id=None,
        status="completed" if payload.status == "completed" else "failed",
        severity="info",
        tags_json=agent.tags_json,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        last_run=datetime.utcnow(),
        total_rules=total,
        passed_rules=passed,
        triggered_by="agent",
        compliance_score=score,
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    # Persist results
    for it in items:
        sr = SRModel(
            organization_id=agent.organization_id,
            scan_id=scan.id,
            rule_id=str(it.get("id") or it.get("rule_id") or secrets.token_hex(6)),
            rule_title=str(it.get("title") or it.get("rule_title") or "rule"),
            severity=str(it.get("severity") or "info"),
            status="passed" if it.get("passed") else "failed",
            passed=bool(it.get("passed")),
            stdout=it.get("stdout"),
            stderr=it.get("stderr"),
            details_json=json.dumps(it.get("details") or {}),
            executed_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            runtime_ms=None,
        )
        session.add(sr)
    # Create report
    report = Report(
        organization_id=agent.organization_id,
        scan_id=scan.id,
        benchmark_id=scan.benchmark_id,
        hostname=scan.hostname,
        score=score,
        summary=f"Agent scan completed with {passed}/{total} passing",
        status="passed" if passed == total and total > 0 else "attention",
        severity=scan.severity,
        tags_json=scan.tags_json,
        last_run=scan.completed_at,
        output_path=None,
    )
    session.add(report)
    session.commit()
    return {"ok": True, "job_id": job.id, "scan_id": scan.id}
