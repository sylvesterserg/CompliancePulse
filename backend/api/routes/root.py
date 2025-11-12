"""Root-level routes for the CompliancePulse API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..dependencies import get_session
from ..models import System

router = APIRouter(tags=["root"])


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "CompliancePulse API", "version": "0.1.0", "status": "running"}


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        session.exec(select(System).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:  # pragma: no cover - defensive logging path
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")
