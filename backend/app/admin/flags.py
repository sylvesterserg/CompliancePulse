from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from ..models import FeatureFlag


def list_feature_flags(session: Session) -> list[FeatureFlag]:
    return session.exec(select(FeatureFlag).order_by(FeatureFlag.key)).all()


def toggle_flag(session: Session, flag_id: int) -> FeatureFlag:
    flag = session.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    flag.enabled = not flag.enabled
    session.add(flag)
    session.commit()
    session.refresh(flag)
    return flag


def create_flag(session: Session, key: str, description: str, enabled: bool) -> FeatureFlag:
    existing = session.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flag already exists")
    flag = FeatureFlag(key=key, description=description, enabled=enabled)
    session.add(flag)
    session.commit()
    session.refresh(flag)
    return flag
