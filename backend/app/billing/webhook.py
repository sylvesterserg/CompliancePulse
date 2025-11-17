"""Stripe webhook processor."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status
from sqlmodel import Session

from .utils import BillingManager, StripeClient


class StripeWebhookProcessor:
    def __init__(self, session: Session, stripe_client: StripeClient | None = None):
        self.session = session
        self.manager = BillingManager(session, stripe_client=stripe_client)

    def handle_request(self, payload: bytes, signature: str | None) -> Dict[str, Any]:
        try:
            event = self.manager.client.construct_event(payload, signature)
        except Exception as exc:  # pragma: no cover - signature failure
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        self.process_event(event)
        return event

    def process_event(self, event: Dict[str, Any]) -> None:
        event_id = event.get("id", "")
        event_type = event.get("type", "unknown")
        stored = self.manager.store_event(event_id, event_type)
        if not stored:
            return
        if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            self.manager.update_subscription_from_event(event)
        elif event_type == "customer.subscription.deleted":
            organization = self.manager.update_subscription_from_event(event)
            if organization:
                organization.plan_status = "canceled"
                self.session.add(organization)
                self.session.commit()
        elif event_type == "invoice.payment_failed":
            data_object = event.get("data", {}).get("object", {})
            self.manager.mark_past_due(data_object.get("customer"))
        elif event_type == "checkout.session.completed":
            self.manager.update_subscription_from_session(event.get("data", {}).get("object", {}))
        else:  # pragma: no cover - informational
            return


__all__ = ["StripeWebhookProcessor"]
