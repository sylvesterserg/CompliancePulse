from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..schemas import ReportView
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_service(session: Session) -> ScanService:
    return ScanService(session)


@router.get("", response_model=List[ReportView])
def list_reports(session: Session = Depends(get_db_session)) -> List[ReportView]:
    return _get_service(session).list_reports()


@router.get("/{report_id}", response_model=ReportView)
def get_report(report_id: int, session: Session = Depends(get_db_session)) -> ReportView:
    try:
        return _get_service(session).get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
