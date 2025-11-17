from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..auth.dependencies import get_current_organization, require_role
from ..models import MembershipRole
from ..schemas import ScheduleCreate, ScheduleView
from ..services.schedule_service import ScheduleService
from .deps import get_db_session

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
