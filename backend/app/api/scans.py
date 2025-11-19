from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json
from sqlmodel import Session

from ..auth.dependencies import get_current_organization, require_role, require_authenticated_user
from ..auth.dependencies import verify_csrf_token as _verify_csrf
from ..models import MembershipRole
from ..schemas import ReportView, ScanDetail, ScanJobView, ScanRequest, ScanSummary
from ..security.api_keys import get_optional_api_key
from ..security.audit import log_action
from ..security.rate_limit import rate_limit
from ..security.utils import mask_secret
from ..services.scan_service import ScanService
from .deps import get_db_session
from . import ui_router as _ui

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


@router.post("/trigger", dependencies=[Depends(_verify_csrf)])
async def trigger_scan_alias(
    request: Request,
    service: ScanService = Depends(_get_service),
    api_key=Depends(get_optional_api_key),
):
    # HTMX/UI form submission: parse form data, enforce CSRF, and return HTML partial
    content_type = (request.headers.get("content-type") or "").lower()
    is_htmx = request.headers.get("hx-request", "").lower() == "true"
    if is_htmx or content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data"):
        form = await request.form()
        hostname = str(form.get("hostname", "")).strip()
        ip = str(form.get("ip", form.get("ip_address", ""))).strip() or None
        benchmark_id = str(form.get("benchmark_id", "")).strip()
        tags = str(form.get("tags", ""))
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if not hostname or not benchmark_id:
            raise HTTPException(status_code=400, detail="Missing required fields")
        payload = ScanRequest(hostname=hostname, ip=ip, benchmark_id=benchmark_id, tags=tag_list)
        detail = service.start_scan(payload)
        log_action(
            action_type="SCAN_TRIGGER",
            resource_type="SCAN",
            resource_id=detail.id,
            request=request,
            user=None,
            org=None,
            metadata={"benchmark_id": benchmark_id, "hostname": hostname, "api_key": mask_secret(api_key.prefix) if api_key else None},
        )
        return _ui._render_scans_table(request, service, modal_reset=True)
    # JSON API: delegate to standard creator
    body = await request.json()
    payload = ScanRequest(**body)
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
