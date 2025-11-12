"""Scan route for CompliancePulse."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from ..dependencies import get_session, json_dumps
from ..models import Report, System

router = APIRouter(tags=["scan"])


class ScanRequest(BaseModel):
    hostname: str
    ip: str | None = None


class ScanResponse(BaseModel):
    hostname: str
    score: int
    issues: list[str]
    scan_time: str


SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/scan", response_model=ScanResponse)
def scan_system(request: ScanRequest, session: SessionDep) -> ScanResponse:
    scan_time = datetime.now().isoformat()
    scan_result = ScanResponse(
        hostname=request.hostname,
        score=87,
        issues=[
            "Password policy does not meet CIS standards",
            "Firewall not configured properly",
            "SSH root login enabled",
            "No automatic security updates configured",
        ],
        scan_time=scan_time,
    )

    existing = session.exec(select(System).where(System.hostname == request.hostname)).first()

    if existing:
        system = existing
        system.last_scan = scan_time
        if request.ip is not None:
            system.ip = request.ip
    else:
        system = System(hostname=request.hostname, ip=request.ip, last_scan=scan_time)
        session.add(system)

    session.commit()
    session.refresh(system)

    report = Report(
        system_id=system.id,
        score=scan_result.score,
        issues_json=json_dumps(scan_result.issues),
        created_at=scan_time,
    )
    session.add(report)
    session.commit()

    return scan_result
