"""Utilities for billing orchestration and Stripe helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlmodel import Session, select

from ..config import settings
from ..models import BillingEvent, Organization
from .plans import PlanDefinition, get_plan, plan_for_price

try:  # pragma: no cover - stripe import guarded for offline testing
    import stripe
except Exception:  # pragma: no cover - fallback to mockable interface
    stripe = None


class StripeClient:
    """Thin wrapper around stripe-python with graceful fallbacks."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.stripe_secret_key
        self.enabled = bool(self.api_key and stripe is not None)
        if self.enabled:
            stripe.api_key = self.api_key

    def create_customer(self, **kwargs: Any) -> Dict[str, Any]:
        if not self.enabled:
            return {"id": f"cus_{uuid4().hex[:14]}", **kwargs}
        return stripe.Customer.create(**kwargs)

    def create_checkout_session(self, **kwargs: Any) -> Dict[str, Any]:
        if not self.enabled:
            session_id = f"cs_test_{uuid4().hex[:14]}"
            return {"id": session_id, "url": kwargs.get("success_url", settings.app_base_url)}
        return stripe.checkout.Session.create(**kwargs)

    def create_portal_session(self, **kwargs: Any) -> Dict[str, Any]:
        if not self.enabled:
            return {"url": kwargs.get("return_url", settings.app_base_url)}
        return stripe.billing_portal.Session.create(**kwargs)

    def construct_event(self, payload: bytes, signature: str | None) -> Dict[str, Any]:
        if not self.enabled or not settings.stripe_webhook_secret:
            return json.loads(payload.decode("utf-8"))
        return stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)


class BillingManager:
    """Coordinates Stripe operations and keeps the organization model in sync."""

    def __init__(self, session: Session, stripe_client: StripeClient | None = None):
        self.session = session
        self.client = stripe_client or StripeClient()

    def ensure_customer(self, organization: Organization) -> str:
        if organization.stripe_customer_id:
            return organization.stripe_customer_id
        customer = self.client.create_customer(
            email=organization.billing_email or "owner@example.com",
            name=organization.name,
            metadata={"organization_id": str(organization.id)},
        )
        organization.mark_plan_status(customer_id=customer.get("id"))
        self.session.add(organization)
        self.session.commit()
        return organization.stripe_customer_id or customer.get("id", "")

    def create_checkout_session(self, organization: Organization, plan: PlanDefinition) -> Dict[str, Any]:
        customer_id = self.ensure_customer(organization)
        success_url = f"{settings.app_base_url}/billing/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{settings.app_base_url}/billing/checkout/canceled"
        return self.client.create_checkout_session(
            success_url=success_url,
            cancel_url=cancel_url,
            mode="subscription",
            client_reference_id=str(organization.id),
            customer=customer_id,
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            allow_promotion_codes=True,
        )

    def create_portal_session(self, organization: Organization) -> Dict[str, Any]:
        customer_id = self.ensure_customer(organization)
        return_url = f"{settings.app_base_url}/billing"
        return self.client.create_portal_session(customer=customer_id, return_url=return_url)

    def store_event(self, event_id: str, event_type: str) -> bool:
        if not event_id:
            return False
        existing = self.session.get(BillingEvent, event_id)
        if existing:
            return False
        self.session.add(BillingEvent(id=event_id, type=event_type))
        self.session.commit()
        return True

    def update_subscription_from_session(self, session_payload: Dict[str, Any]) -> Organization | None:
        customer_id = session_payload.get("customer")
        organization = self._get_org_by_customer(customer_id)
        if not organization:
            return None
        subscription_id = session_payload.get("subscription")
        plan = plan_for_price(self._extract_price_from_session(session_payload))
        if plan:
            organization.mark_plan_status(plan_name=plan.key)
        if subscription_id:
            organization.stripe_subscription_id = subscription_id
        if session_payload.get("status"):
            organization.plan_status = session_payload["status"]
        organization.updated_at = datetime.utcnow()
        self.session.add(organization)
        self.session.commit()
        return organization

    def update_subscription_from_event(self, event_payload: Dict[str, Any]) -> Organization | None:
        data_object = event_payload.get("data", {}).get("object", {})
        customer_id = data_object.get("customer")
        organization = self._get_org_by_customer(customer_id)
        if not organization:
            return None
        plan = plan_for_price(self._extract_price_from_subscription(data_object))
        if plan:
            organization.current_plan = plan.key
        status = data_object.get("status") or event_payload.get("type")
        organization.plan_status = status or organization.plan_status
        if data_object.get("cancel_at_period_end"):
            organization.plan_status = "canceled"
        subscription_id = data_object.get("id")
        if subscription_id:
            organization.stripe_subscription_id = subscription_id
        period_end = data_object.get("current_period_end")
        if period_end:
            organization.next_billing_date = datetime.fromtimestamp(period_end, tz=timezone.utc).replace(tzinfo=None)
        trial_end = data_object.get("trial_end")
        if trial_end:
            organization.trial_end = datetime.fromtimestamp(trial_end, tz=timezone.utc).replace(tzinfo=None)
        organization.updated_at = datetime.utcnow()
        self.session.add(organization)
        self.session.commit()
        return organization

    def mark_past_due(self, customer_id: str | None) -> None:
        organization = self._get_org_by_customer(customer_id)
        if not organization:
            return
        organization.plan_status = "past_due"
        organization.updated_at = datetime.utcnow()
        self.session.add(organization)
        self.session.commit()

    def _get_org_by_customer(self, customer_id: str | None) -> Organization | None:
        if not customer_id:
            return None
        statement = select(Organization).where(Organization.stripe_customer_id == customer_id)
        return self.session.exec(statement).first()

    def _extract_price_from_session(self, session_payload: Dict[str, Any]) -> Optional[str]:
        display_items = session_payload.get("display_items") or []
        if display_items:
            price = display_items[0].get("price")
            if isinstance(price, dict):
                return price.get("id")
        line_items = session_payload.get("line_items") or []
        if line_items:
            price = line_items[0].get("price")
            if isinstance(price, dict):
                return price.get("id")
        price_id = session_payload.get("subscription_data", {}).get("items", [{}])[0].get("price")
        if isinstance(price_id, dict):
            return price_id.get("id")
        return price_id

    def _extract_price_from_subscription(self, data_object: Dict[str, Any]) -> Optional[str]:
        items = data_object.get("items", {}).get("data", [])
        if not items:
            return None
        price = items[0].get("price")
        if isinstance(price, dict):
            return price.get("id")
        return price


def get_billing_state(session: Session) -> Organization | None:
    return session.exec(select(Organization).order_by(Organization.created_at)).first()


def plan_allows_feature(organization: Organization, feature_name: str) -> bool:
    if organization.is_trial_active():
        return True
    plan = get_plan(organization.current_plan)
    limit = plan.features.get(feature_name)
    if limit in (True, "unlimited"):
        return True
    if isinstance(limit, int):
        return limit > 0
    return False


def feature_limit(organization: Organization, feature_name: str) -> Any:
    plan = get_plan(organization.current_plan)
    return plan.features.get(feature_name)


def build_fake_checkout_session(organization: Organization, plan: PlanDefinition) -> Dict[str, Any]:
    session_id = f"cs_test_{uuid4().hex[:10]}"
    return {
        "id": session_id,
        "object": "checkout.session",
        "customer": organization.stripe_customer_id or f"cus_{uuid4().hex[:10]}",
        "subscription": f"sub_{uuid4().hex[:10]}",
        "line_items": [{"price": {"id": plan.stripe_price_id}}],
        "status": "complete",
    }


def inject_test_event(
    session: Session,
    *,
    plan_key: str = "pro",
    event_type: str = "customer.subscription.updated",
    customer_id: str | None = None,
) -> Dict[str, Any]:
    organization = get_billing_state(session)
    if not organization:
        organization = Organization(name="Test Org", slug=f"org-{uuid4().hex[:6]}")
        session.add(organization)
        session.commit()
        session.refresh(organization)
    customer_id = customer_id or organization.stripe_customer_id or f"cus_{uuid4().hex[:10]}"
    organization.stripe_customer_id = customer_id
    plan = get_plan(plan_key)
    event_id = f"evt_{uuid4().hex[:14]}"
    payload = {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": f"sub_{uuid4().hex[:10]}",
                "customer": customer_id,
                "status": "active",
                "items": {"data": [{"price": {"id": plan.stripe_price_id}}]},
                "current_period_end": int(datetime.utcnow().timestamp()) + 3600,
            }
        },
    }
    session.add(organization)
    session.commit()
    from .webhook import StripeWebhookProcessor

    processor = StripeWebhookProcessor(session)
    processor.process_event(payload)
    return payload


__all__ = [
    "BillingManager",
    "StripeClient",
    "build_fake_checkout_session",
    "feature_limit",
    "get_billing_state",
    "inject_test_event",
    "plan_allows_feature",
]
