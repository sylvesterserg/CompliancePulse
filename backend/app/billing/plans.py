"""Static plan definitions and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from ..config import settings


@dataclass(frozen=True)
class PlanDefinition:
    key: str
    name: str
    price_monthly: int
    stripe_price_id: str
    description: str
    features: Dict[str, Any] = field(default_factory=dict)
    highlight: str | None = None

    def feature_label(self, feature: str) -> str:
        value = self.features.get(feature)
        if value == "unlimited":
            return "Unlimited"
        if value is True:
            return "Included"
        if value is False:
            return "Not included"
        if isinstance(value, int):
            return f"Up to {value}"
        if isinstance(value, str):
            return value.title()
        return "Included"


PLAN_DEFINITIONS: Dict[str, PlanDefinition] = {
    "free": PlanDefinition(
        key="free",
        name="Free",
        price_monthly=0,
        stripe_price_id=settings.stripe_price_free,
        description="Starter plan for small teams evaluating CompliancePulse.",
        features={
            "rules": 3,
            "members": 1,
            "schedules": 1,
            "ai_summaries": False,
            "priority_queue": False,
        },
        highlight="Great for evaluation environments",
    ),
    "pro": PlanDefinition(
        key="pro",
        name="Pro",
        price_monthly=9900,
        stripe_price_id=settings.stripe_price_pro,
        description="Advanced automation and AI summaries for growing teams.",
        features={
            "rules": 100,
            "members": 10,
            "schedules": "unlimited",
            "ai_summaries": True,
            "priority_queue": False,
        },
        highlight="Most popular",
    ),
    "enterprise": PlanDefinition(
        key="enterprise",
        name="Enterprise",
        price_monthly=0,
        stripe_price_id=settings.stripe_price_enterprise,
        description="Unlimited automation with dedicated priority workers.",
        features={
            "rules": "unlimited",
            "members": "unlimited",
            "schedules": "unlimited",
            "ai_summaries": True,
            "priority_queue": True,
        },
        highlight="Custom pricing",
    ),
}


def list_plans() -> List[PlanDefinition]:
    return list(PLAN_DEFINITIONS.values())


def get_plan(plan_name: str) -> PlanDefinition:
    key = plan_name.lower()
    if key not in PLAN_DEFINITIONS:
        raise KeyError(f"Unknown plan '{plan_name}'")
    return PLAN_DEFINITIONS[key]


def plan_for_price(price_id: str | None) -> PlanDefinition | None:
    if not price_id:
        return None
    for plan in PLAN_DEFINITIONS.values():
        if plan.stripe_price_id == price_id:
            return plan
    return None


def included_features(plan: PlanDefinition) -> Iterable[str]:
    for feature, value in plan.features.items():
        yield feature, value
