"""FastAPI dependencies for billing enforcement."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, func, select

from ..api.deps import get_db_session
from ..models import Organization, Rule, Schedule
from .plans import get_plan


def get_current_organization(session: Session = Depends(get_db_session)) -> Organization:
    organization = session.exec(select(Organization).order_by(Organization.created_at)).first()
    if organization:
        return organization
    organization = Organization(
        name="Default Organization",
        slug="default",
        billing_email="owner@example.com",
    )
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


def require_owner_access(request: Request) -> None:
    from ..config import settings

    token = settings.billing_owner_token
    if not token:
        return
    provided = request.headers.get("X-Billing-Owner") or request.query_params.get("owner_token")
    if provided != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner permissions required")


def require_active_subscription(
    organization: Organization = Depends(get_current_organization),
) -> Organization:
    if not organization.is_subscription_active():
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Subscription inactive")
    return organization


def require_feature(
    feature_name: str,
    usage_provider: Callable[[Session, Organization], int] | None = None,
) -> Callable[[Session, Organization], Organization]:
    def dependency(
        session: Session = Depends(get_db_session),
        organization: Organization = Depends(require_active_subscription),
    ) -> Organization:
        if organization.is_trial_active():
            return organization
        plan = get_plan(organization.current_plan)
        limit = plan.features.get(feature_name)
        if limit in (True, "unlimited"):
            return organization
        if limit is False or limit is None:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"{feature_name.replace('_', ' ').title()} not available on {plan.name}",
            )
        usage = 0
        if usage_provider:
            usage = usage_provider(session, organization)
        if isinstance(limit, int) and usage >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Reached limit of {limit} for {feature_name}",
            )
        return organization

    return dependency


def count_rules(session: Session, organization: Organization | None = None) -> int:
    return session.exec(select(func.count(Rule.id))).one()


def count_schedules(session: Session, organization: Organization | None = None) -> int:
    return session.exec(select(func.count(Schedule.id))).one()


