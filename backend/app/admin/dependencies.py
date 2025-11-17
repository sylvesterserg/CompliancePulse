from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..api.deps import get_db_session
from ..config import settings
from ..models import User

_templates: Jinja2Templates | None = None


def get_admin_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory=str(settings.frontend_template_dir))
        _templates.env.globals.update({"app_name": settings.app_name})
    return _templates


def get_current_user(
    session: Session = Depends(get_db_session),
    user_id_header: int | None = Header(default=None, alias="X-User-ID"),
) -> User:
    if user_id_header is not None:
        user = session.get(User, user_id_header)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if not user.is_active or user.is_locked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        return user

    fallback = (
        session.exec(select(User).where(User.super_admin == True).order_by(User.id)).first()  # noqa: E712
    )
    if fallback:
        return fallback
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user context")


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin role required")
    return user


def admin_base_context(request: Request, nav_active: str, session: Session, user: User) -> dict:
    return {
        "request": request,
        "nav_active": nav_active,
        "current_user": user,
        "environment": settings.environment,
        "health_status": _health_status(session),
        "page_title": nav_active.replace("-", " ").title(),
    }


def _health_status(session: Session) -> dict:
    try:
        session.exec(select(User.id).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "unreachable"}
