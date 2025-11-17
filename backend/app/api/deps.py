from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session

from ..auth.dependencies import get_current_organization
from ..database import get_session


def get_db_session(
    session: Session = Depends(get_session),
    organization = Depends(get_current_organization),
) -> Session:
    session.info["organization_id"] = organization.id
    return session
