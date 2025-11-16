from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..schemas import ReportView, ScanDetail, ScanRequest, ScanSummary
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/scans", tags=["scans"])


def _get_service(session: Session) -> ScanService:
    return ScanService(session)


@router.post("", response_model=ScanDetail)
def create_scan(
    payload: ScanRequest,
    session: Session = Depends(get_db_session),
) -> ScanDetail:
    try:
        return _get_service(session).start_scan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=List[ScanSummary])
def list_scans(session: Session = Depends(get_db_session)) -> List[ScanSummary]:
    return _get_service(session).list_scans()


@router.get("/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: int, session: Session = Depends(get_db_session)) -> ScanDetail:
    try:
        return _get_service(session).get_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{scan_id}/report", response_model=ReportView)
def get_scan_report(scan_id: int, session: Session = Depends(get_db_session)) -> ReportView:
    try:
        return _get_service(session).get_report_for_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
