from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session

from ..database import get_session


def get_db_session(session: Session = Depends(get_session)) -> Session:
    return session
