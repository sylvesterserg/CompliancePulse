from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..billing.dependencies import count_schedules, require_feature
from ..schemas import ScheduleCreate, ScheduleView
from ..services.schedule_service import ScheduleService
from .deps import get_db_session

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _get_service(session: Session) -> ScheduleService:
    return ScheduleService(session)


@router.get("", response_model=List[ScheduleView])
def list_schedules(session: Session = Depends(get_db_session)) -> List[ScheduleView]:
    return _get_service(session).list_schedules()


@router.post("/create", response_model=ScheduleView)
def create_schedule(
    payload: ScheduleCreate,
    session: Session = Depends(get_db_session),
    _: Session = Depends(require_feature("schedules", count_schedules)),
) -> ScheduleView:
    try:
        return _get_service(session).create_schedule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, session: Session = Depends(get_db_session)) -> dict[str, str]:
    try:
        _get_service(session).delete_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}
