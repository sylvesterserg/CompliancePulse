from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..auth.dependencies import get_current_organization, require_role
from ..models import MembershipRole
from ..schemas import ReportView, ScanDetail, ScanJobView, ScanRequest, ScanSummary
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/scans", tags=["scans"])


def _get_service(
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> ScanService:
    return ScanService(session, organization_id=organization.id)


@router.post(
    "",
    response_model=ScanDetail,
    dependencies=[Depends(require_role(MembershipRole.ADMIN))],
)
def create_scan(
    payload: ScanRequest,
    service: ScanService = Depends(_get_service),
) -> ScanDetail:
    try:
        return service.start_scan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=List[ScanSummary])
def list_scans(service: ScanService = Depends(_get_service)) -> List[ScanSummary]:
    return service.list_scans()


@router.get("/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: int, service: ScanService = Depends(_get_service)) -> ScanDetail:
    try:
        return service.get_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{scan_id}/report", response_model=ReportView)
def get_scan_report(scan_id: int, service: ScanService = Depends(_get_service)) -> ReportView:
    try:
        return service.get_report_for_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/trigger/group/{group_id}",
    response_model=ScanJobView,
    dependencies=[Depends(require_role(MembershipRole.ADMIN))],
)
def trigger_group_scan(
    group_id: int,
    service: ScanService = Depends(_get_service),
) -> ScanJobView:
    try:
        return service.enqueue_group_scan(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
