from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..auth.dependencies import get_current_organization
from ..schemas import ReportView
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_service(
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> ScanService:
    return ScanService(session, organization_id=organization.id)


@router.get("", response_model=List[ReportView])
def list_reports(service: ScanService = Depends(_get_service)) -> List[ReportView]:
    return service.list_reports()


@router.get("/{report_id}", response_model=ReportView)
def get_report(report_id: int, service: ScanService = Depends(_get_service)) -> ReportView:
    try:
        return service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
