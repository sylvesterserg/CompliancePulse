from __future__ import annotations

from typing import List

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import MembershipRole, Organization, User, UserOrganization
from .utils import SessionData


ROLE_WEIGHT = {
    MembershipRole.MEMBER: 1,
    MembershipRole.ADMIN: 2,
    MembershipRole.OWNER: 3,
}


def get_session_data(request: Request) -> SessionData:
    session_data: SessionData | None = getattr(request.state, "session_data", None)
    if not session_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session unavailable")
    return session_data


def get_optional_user(
    request: Request,
    session_data: SessionData = Depends(get_session_data),
    db: Session = Depends(get_session),
) -> User | None:
    if hasattr(request.state, "current_user"):
        return getattr(request.state, "current_user")
    if not session_data.user_id:
        return None
    user = db.get(User, session_data.user_id)
    if not user or not user.is_active:
        return None
    request.state.current_user = user
    return user


def require_authenticated_user(
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def list_user_organizations(
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_session),
) -> List[Organization]:
    statement = (
        select(Organization)
        .join(UserOrganization, UserOrganization.organization_id == Organization.id)
        .where(UserOrganization.user_id == user.id)
        .order_by(Organization.name)
    )
    return db.exec(statement).all()


def _persist_session(request: Request, session_data: SessionData) -> None:
    request.state.session_data = session_data
    request.state.session_dirty = True


def get_current_organization(
    request: Request,
    session_data: SessionData = Depends(get_session_data),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_session),
) -> Organization:
    org_id = session_data.organization_id
    if not org_id:
        membership = (
            db.exec(
                select(UserOrganization).where(UserOrganization.user_id == user.id).order_by(UserOrganization.joined_at)
            ).first()
        )
        if not membership:
            raise HTTPException(status_code=400, detail="User is not assigned to an organization")
        org_id = membership.organization_id
        session_data.organization_id = org_id
        _persist_session(request, session_data)
    organization = db.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    request.state.current_organization = organization
    return organization


def get_current_membership(
    request: Request,
    user: User = Depends(require_authenticated_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_session),
) -> UserOrganization:
    membership = (
        db.exec(
            select(UserOrganization)
            .where(
                (UserOrganization.user_id == user.id)
                & (UserOrganization.organization_id == organization.id)
            )
            .limit(1)
        ).first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")
    request.state.current_membership = membership
    return membership


def require_role(role: MembershipRole | str):
    required = MembershipRole(role)

    def _checker(membership: UserOrganization = Depends(get_current_membership)) -> None:
        if ROLE_WEIGHT[membership.role] < ROLE_WEIGHT[required]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return _checker


async def verify_csrf_token(
    request: Request,
    session_data: SessionData = Depends(get_session_data),
) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    token = request.headers.get(settings.csrf_header_name)
    if not token:
        if hasattr(request.state, "cached_form"):
            form = request.state.cached_form
        else:
            form = await request.form()
            request.state.cached_form = form
        token = form.get("csrf_token") if form else None
    if not token or token != session_data.csrf_token:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


__all__ = [
    "get_session_data",
    "get_optional_user",
    "require_authenticated_user",
    "get_current_organization",
    "get_current_membership",
    "require_role",
    "verify_csrf_token",
    "list_user_organizations",
]
