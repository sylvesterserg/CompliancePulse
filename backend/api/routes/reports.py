"""Report related API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..dependencies import get_session, json_loads
from ..models import Report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(limit: int = 10, session: Session = Depends(get_session)) -> dict[str, object]:
    reports = session.exec(select(Report).limit(limit)).all()
    enriched = [
        {
            **report.model_dump(),
            "issues": json_loads(report.issues_json) if report.issues_json else [],
        }
        for report in reports
    ]
    return {"reports": enriched, "count": len(reports)}
