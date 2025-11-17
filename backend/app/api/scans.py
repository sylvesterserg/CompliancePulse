from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..billing.dependencies import get_current_organization, require_active_subscription
from ..models import Organization
from ..schemas import ReportView, ScanDetail, ScanJobView, ScanRequest, ScanSummary
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/scans", tags=["scans"])


def _get_service(session: Session, organization: Organization | None = None) -> ScanService:
    return ScanService(session, organization=organization)


@router.post("", response_model=ScanDetail)
def create_scan(
    payload: ScanRequest,
    session: Session = Depends(get_db_session),
    organization: Organization = Depends(require_active_subscription),
) -> ScanDetail:
    try:
        return _get_service(session, organization=organization).start_scan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=List[ScanSummary])
def list_scans(session: Session = Depends(get_db_session)) -> List[ScanSummary]:
    organization = get_current_organization(session)
    return _get_service(session, organization=organization).list_scans()


@router.get("/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: int, session: Session = Depends(get_db_session)) -> ScanDetail:
    try:
        organization = get_current_organization(session)
        return _get_service(session, organization=organization).get_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{scan_id}/report", response_model=ReportView)
def get_scan_report(scan_id: int, session: Session = Depends(get_db_session)) -> ReportView:
    try:
        organization = get_current_organization(session)
        return _get_service(session, organization=organization).get_report_for_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/trigger/group/{group_id}", response_model=ScanJobView)
def trigger_group_scan(
    group_id: int,
    session: Session = Depends(get_db_session),
    organization: Organization = Depends(require_active_subscription),
) -> ScanJobView:
    try:
        return _get_service(session, organization=organization).enqueue_group_scan(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
