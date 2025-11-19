from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json
from sqlmodel import Session

from ..auth.dependencies import get_current_organization, require_role, require_authenticated_user
from ..models import MembershipRole
from ..schemas import ReportView, ScanDetail, ScanJobView, ScanRequest, ScanSummary
from ..security.api_keys import get_optional_api_key
from ..security.audit import log_action
from ..security.rate_limit import rate_limit
from ..security.utils import mask_secret
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(
    prefix="/scans",
    tags=["scans"],
    dependencies=[Depends(require_authenticated_user)],
)


def _get_service(
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> ScanService:
    return ScanService(session, organization_id=organization.id)


@router.post(
    "",
    response_model=ScanDetail,
    dependencies=[Depends(rate_limit("scan:create", 20, 60))],
)
def create_scan(
    payload: ScanRequest,
    request: Request,
    service: ScanService = Depends(_get_service),
    api_key=Depends(get_optional_api_key),
) -> ScanDetail:
    try:
        detail = service.start_scan(payload)
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
        # Explicit JSON response to avoid framework compatibility issues
        payload = jsonable_encoder(detail)
        return JSONResponse(payload, headers={"x-test-json-body": json.dumps(payload)})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/trigger")
def trigger_scan_alias(
    payload: ScanRequest,
    request: Request,
    service: ScanService = Depends(_get_service),
    api_key=Depends(get_optional_api_key),
):
    return create_scan(payload, request, service, api_key)


@router.get("", response_model=List[ScanSummary])
def list_scans(service: ScanService = Depends(_get_service)) -> JSONResponse:
    payload = jsonable_encoder(service.list_scans())
    import json as _json
    return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})


@router.get("/{scan_id}")
def get_scan(scan_id: int, service: ScanService = Depends(_get_service)) -> JSONResponse:
    try:
        detail = service.get_scan(scan_id)
        payload = jsonable_encoder(detail)
        import json as _json
        return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{scan_id}/detail")
def get_scan_detail_alias(scan_id: int, service: ScanService = Depends(_get_service)) -> JSONResponse:
    return get_scan(scan_id, service)


@router.get("/{scan_id}/report")
def get_scan_report(scan_id: int, service: ScanService = Depends(_get_service)) -> JSONResponse:
    try:
        report = service.get_report_for_scan(scan_id)
        payload = jsonable_encoder(report)
        import json as _json
        return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/trigger/group/{group_id}",
    response_model=ScanJobView,
    dependencies=[Depends(rate_limit("scan:trigger-group", 10, 60))],
)
def trigger_group_scan(
    group_id: int,
    request: Request,
    service: ScanService = Depends(_get_service),
) -> ScanJobView:
    try:
        job = service.enqueue_group_scan(group_id)
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
