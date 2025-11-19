from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session

from ..auth.dependencies import get_current_organization, require_role, verify_csrf_token
from ..models import MembershipRole
from ..schemas import ScheduleCreate, ScheduleView
from ..services.schedule_service import ScheduleService
from .deps import get_db_session
from . import ui_router as _ui

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _get_service(
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> ScheduleService:
    return ScheduleService(session, organization_id=organization.id)


@router.get("", response_model=List[ScheduleView])
def list_schedules(service: ScheduleService = Depends(_get_service)) -> List[ScheduleView]:
    return service.list_schedules()


@router.post(
    "/create",
    response_model=ScheduleView,
    dependencies=[Depends(require_role(MembershipRole.ADMIN))],
)
def create_schedule(
    payload: ScheduleCreate,
    service: ScheduleService = Depends(_get_service),
) -> ScheduleView:
    try:
        return service.create_schedule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{schedule_id}",
    dependencies=[Depends(require_role(MembershipRole.ADMIN))],
)
def delete_schedule(schedule_id: int, service: ScheduleService = Depends(_get_service)) -> dict[str, str]:
    try:
        service.delete_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


# HTML modal endpoints for UI
@router.get("/modal/new", response_class=HTMLResponse)
def schedule_modal_new(
    request: Request,
    service: ScheduleService = Depends(_get_service),
):
    context = {
        "request": request,
        "rule_groups": service.list_rule_groups(),
        "csrf_token": _ui._csrf_token(request),
    }
    return _ui._templates().TemplateResponse("modals/schedule_new.html", context)


@router.get("/modal/edit/{schedule_id}", response_class=HTMLResponse)
def schedule_modal_edit(
    schedule_id: int,
    request: Request,
    service: ScheduleService = Depends(_get_service),
):
    schedules = service.list_schedules()
    match = next((s for s in schedules if s.id == schedule_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Schedule not found")
    context = {
        "request": request,
        "schedule": match,
        "rule_groups": service.list_rule_groups(),
        "csrf_token": _ui._csrf_token(request),
    }
    return _ui._templates().TemplateResponse("modals/schedule_edit.html", context)


@router.get("/modal/delete/{schedule_id}", response_class=HTMLResponse)
def schedule_modal_delete(
    schedule_id: int,
    request: Request,
    service: ScheduleService = Depends(_get_service),
):
    schedules = service.list_schedules()
    match = next((s for s in schedules if s.id == schedule_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Schedule not found")
    context = {
        "request": request,
        "schedule": match,
        "csrf_token": _ui._csrf_token(request),
    }
    return _ui._templates().TemplateResponse("modals/schedule_delete.html", context)


@router.post(
    "/{schedule_id}/update",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token), Depends(require_role(MembershipRole.ADMIN))],
)
async def update_schedule(
    schedule_id: int,
    request: Request,
    service: ScheduleService = Depends(_get_service),
):
    form = await request.form()
    # Extract with defaults
    name = str(form.get("name", "")).strip()
    frequency = str(form.get("frequency", "daily")).strip() or "daily"
    interval = form.get("interval_minutes")
    interval_minutes = int(interval) if interval else None
    group_id = int(form.get("group_id", 0))
    enabled = True if form.get("enabled") in ("on", "true", "1") else False
    if not name or not group_id:
        raise HTTPException(status_code=400, detail="Name and group are required")
    # Fetch and update schedule
    from ..models import Schedule as _Schedule
    sched = service.session.get(_Schedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    sched.name = name
    sched.group_id = group_id
    sched.frequency = frequency
    if interval_minutes is not None:
        sched.interval_minutes = max(interval_minutes, 5)
    sched.enabled = enabled
    service.session.add(sched)
    service.session.commit()
    # Re-render schedules table
    return _ui._render_schedules_table(request, service, modal_reset=True)


@router.post(
    "/{schedule_id}/delete",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token), Depends(require_role(MembershipRole.ADMIN))],
)
async def delete_schedule_via_post(
    schedule_id: int,
    request: Request,
    service: ScheduleService = Depends(_get_service),
):
    try:
        service.delete_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ui._render_schedules_table(request, service, modal_reset=True)


# Compatibility aliases for scan API naming
@router.post("/trigger")
def trigger_alias(payload: ScheduleCreate, service: ScheduleService = Depends(_get_service)):
    return create_schedule(payload, service)
