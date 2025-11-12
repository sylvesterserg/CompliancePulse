"""System related API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..dependencies import get_session
from ..models import System

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("")
def list_systems(session: Session = Depends(get_session)) -> dict[str, object]:
    systems = session.exec(select(System)).all()
    return {"systems": systems, "count": len(systems)}


@router.get("/{system_id}")
def get_system(system_id: int, session: Session = Depends(get_session)) -> System:
    system = session.get(System, system_id)
    if not system:
        raise HTTPException(status_code=404, detail="System not found")
    return system
