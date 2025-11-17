from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from ..schemas import ReportView, ScanDetail, ScanJobView, ScanRequest, ScanSummary
from ..security.api_keys import get_optional_api_key
from ..security.audit import log_action
from ..security.rate_limit import rate_limit
from ..security.utils import mask_secret
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/scans", tags=["scans"])


def _get_service(session: Session) -> ScanService:
    return ScanService(session)


@router.post(
    "",
    response_model=ScanDetail,
    dependencies=[Depends(rate_limit("scan:create", 20, 60))],
)
def create_scan(
    payload: ScanRequest,
    session: Session = Depends(get_db_session),
    request: Request | None = None,
    api_key=Depends(get_optional_api_key),
) -> ScanDetail:
    try:
        detail = _get_service(session).start_scan(payload)
        log_action(
            action_type="SCAN_TRIGGER",
            resource_type="SCAN",
            resource_id=detail.id,
            request=request,
            user=None,
            org=None,
            metadata={
                "benchmark_id": payload.benchmark_id,
                "hostname": payload.hostname,
                "api_key": mask_secret(api_key.prefix) if api_key else None,
            },
        )
        return detail
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


@router.post(
    "/trigger/group/{group_id}",
    response_model=ScanJobView,
    dependencies=[Depends(rate_limit("scan:trigger-group", 10, 60))],
)
def trigger_group_scan(
    group_id: int,
    session: Session = Depends(get_db_session),
    request: Request | None = None,
) -> ScanJobView:
    try:
        job = _get_service(session).enqueue_group_scan(group_id)
        log_action(
            action_type="SCAN_TRIGGER_GROUP",
            resource_type="RULE_GROUP",
            resource_id=group_id,
            request=request,
            user=None,
            org=None,
            metadata={"job_id": job.id},
        )
        return job
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
