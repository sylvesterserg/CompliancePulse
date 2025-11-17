from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Field, SQLModel


class Benchmark(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    title: str
    description: str
    version: str
    os_target: str
    maintainer: Optional[str] = None
    source: Optional[str] = None
    tags_json: str = Field(default="[]")
    schema_version: str = "0.3"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Rule(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    benchmark_id: str = Field(foreign_key="benchmark.id", index=True)
    title: str
    description: str
    severity: str
    remediation: str
    references_json: str = Field(default="[]")
    metadata_json: str = Field(default="{}")
    tags_json: str = Field(default="[]")
    check_type: str
    command: str
    expect_type: str
    expect_value: str
    timeout_seconds: int = 10
    status: str = Field(default="active")
    last_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RuleGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    benchmark_id: str = Field(foreign_key="benchmark.id", index=True)
    description: Optional[str] = None
    rule_ids_json: str = Field(default="[]")
    default_hostname: str = "localhost"
    default_ip: Optional[str] = None
    tags_json: str = Field(default="[]")
    last_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Scan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hostname: str
    ip: Optional[str] = None
    benchmark_id: str = Field(foreign_key="benchmark.id")
    group_id: Optional[int] = Field(default=None, foreign_key="rulegroup.id")
    status: str = Field(default="pending")
    severity: str = Field(default="info")
    tags_json: str = Field(default="[]")
    summary: Optional[str] = None
    ai_summary_json: str = Field(default="{}")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    total_rules: int = 0
    passed_rules: int = 0
    output_path: Optional[str] = None
    triggered_by: str = Field(default="manual")
    compliance_score: float = 0.0


class ScanResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    rule_id: str = Field(foreign_key="rule.id")
    rule_title: str
    severity: str
    status: str = Field(default="pending")
    passed: bool = False
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    details_json: str = Field(default="{}")
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    runtime_ms: Optional[int] = None


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id")
    benchmark_id: str = Field(foreign_key="benchmark.id")
    hostname: str
    score: float
    summary: str
    status: str = Field(default="generated")
    severity: str = Field(default="info")
    tags_json: str = Field(default="[]")
    output_path: Optional[str] = None
    last_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    key_findings_json: str = Field(default="[]")
    remediations_json: str = Field(default="[]")


class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    group_id: int = Field(foreign_key="rulegroup.id")
    frequency: str = Field(default="daily")
    interval_minutes: int = Field(default=1440)
    enabled: bool = Field(default=True)
    timezone: str = Field(default="UTC")
    next_run: Optional[datetime] = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=5))
    last_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScanJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="rulegroup.id")
    schedule_id: Optional[int] = Field(default=None, foreign_key="schedule.id")
    hostname: str
    triggered_by: str = Field(default="scheduler")
    status: str = Field(default="pending")
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scan_id: Optional[int] = Field(default=None, foreign_key="scan.id")


def _default_trial_end() -> datetime:
    return datetime.utcnow() + timedelta(days=14)


class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, sa_column_kwargs={"unique": True})
    billing_email: Optional[str] = None
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
    current_plan: str = Field(default="free")
    plan_status: str = Field(default="trialing")
    trial_end: datetime = Field(default_factory=_default_trial_end)
    next_billing_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_trial_active(self) -> bool:
        return bool(self.trial_end and self.trial_end > datetime.utcnow())

    def days_remaining_in_trial(self) -> int:
        if not self.trial_end:
            return 0
        remaining = (self.trial_end - datetime.utcnow()).days
        return max(remaining, 0)

    def is_subscription_active(self) -> bool:
        if self.is_trial_active():
            return True
        return self.plan_status in {"active", "trialing"}

    def mark_plan_status(
        self,
        *,
        plan_name: str | None = None,
        status: str | None = None,
        trial_end: datetime | None = None,
        next_billing_date: datetime | None = None,
        subscription_id: str | None = None,
        customer_id: str | None = None,
    ) -> None:
        if plan_name:
            self.current_plan = plan_name
        if status:
            self.plan_status = status
        if trial_end:
            self.trial_end = trial_end
        if next_billing_date:
            self.next_billing_date = next_billing_date
        if subscription_id is not None:
            self.stripe_subscription_id = subscription_id
        if customer_id is not None:
            self.stripe_customer_id = customer_id
        self.updated_at = datetime.utcnow()


class BillingEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
