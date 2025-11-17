"""Billing routes."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from ..config import settings
from ..models import Rule
from ..api.deps import get_db_session
from .dependencies import (
    count_rules,
    count_schedules,
    get_current_organization,
    require_owner_access,
)
from .plans import get_plan, list_plans
from .utils import BillingManager
from .webhook import StripeWebhookProcessor

router = APIRouter(prefix="/billing", tags=["billing"])

_templates_instance: Jinja2Templates | None = None


def _templates() -> Jinja2Templates:
    global _templates_instance
    if _templates_instance is None:
        _templates_instance = Jinja2Templates(directory=str(settings.frontend_template_dir))
        _templates_instance.env.globals.update({"app_name": settings.app_name})
    return _templates_instance


def _health_status(session: Session) -> Dict[str, str]:
    try:
        session.exec(select(func.count(Rule.id)).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception:  # pragma: no cover - defensive
        return {"status": "degraded", "database": "unreachable"}


@router.get("", response_class=HTMLResponse)
async def billing_index(
    request: Request,
    session: Session = Depends(get_db_session),
    organization=Depends(get_current_organization),
    _: None = Depends(require_owner_access),
) -> HTMLResponse:
    try:
        current_plan = get_plan(organization.current_plan)
    except KeyError:
        current_plan = get_plan("free")
    usage = {
        "rules": count_rules(session, organization),
        "schedules": count_schedules(session, organization),
    }
    context = {
        "request": request,
        "nav_active": "billing",
        "environment": settings.environment,
        "health_status": _health_status(session),
        "organization": organization,
        "current_plan": current_plan,
        "plans": list_plans(),
        "usage": usage,
        "trial_days": organization.days_remaining_in_trial(),
        "plan_status": organization.plan_status,
        "next_billing_date": organization.next_billing_date,
        "page_title": "Billing",
        "stripe_configured": bool(settings.stripe_secret_key),
    }
    return _templates().TemplateResponse("billing/index.html", context)


@router.post("/subscribe/{plan_name}")
async def subscribe_to_plan(
    plan_name: str,
    session: Session = Depends(get_db_session),
    organization=Depends(get_current_organization),
    _: None = Depends(require_owner_access),
) -> RedirectResponse:
    try:
        plan = get_plan(plan_name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    manager = BillingManager(session)
    checkout = manager.create_checkout_session(organization, plan)
    url = checkout.get("url")
    if not url:
        raise HTTPException(status_code=500, detail="Unable to create checkout session")
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/portal")
async def billing_portal(
    request: Request,
    session: Session = Depends(get_db_session),
    organization=Depends(get_current_organization),
    _: None = Depends(require_owner_access),
) -> RedirectResponse:
    manager = BillingManager(session)
    portal = manager.create_portal_session(organization)
    url = portal.get("url")
    if not url:
        raise HTTPException(status_code=500, detail="Billing portal unavailable")
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success(
    request: Request,
    session: Session = Depends(get_db_session),
    organization=Depends(get_current_organization),
) -> HTMLResponse:
    context = {
        "request": request,
        "nav_active": "billing",
        "environment": settings.environment,
        "health_status": _health_status(session),
        "organization": organization,
        "page_title": "Checkout Success",
    }
    return _templates().TemplateResponse("billing/checkout_success.html", context)


@router.get("/checkout/canceled", response_class=HTMLResponse)
async def checkout_canceled(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    context = {
        "request": request,
        "nav_active": "billing",
        "environment": settings.environment,
        "health_status": _health_status(session),
        "page_title": "Checkout Canceled",
    }
    return _templates().TemplateResponse("billing/checkout_canceled.html", context)


@router.get("/modal/upgrade", response_class=HTMLResponse)
async def upgrade_modal(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    context = {"request": request, "plans": list_plans()}
    return _templates().TemplateResponse("modals/upgrade_prompt.html", context)


@router.post("/webhook")
async def billing_webhook(
    request: Request,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    processor = StripeWebhookProcessor(session)
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    processor.handle_request(payload, signature)
    return JSONResponse({"status": "received"})

