from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, sa_column_kwargs={"unique": True})
    plan_tier: str = Field(default="starter")
    seat_limit: int = Field(default=5)
    is_active: bool = Field(default=True)
    subscription_status: str = Field(default="trialing")
    subscription_renews_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    suspended_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, sa_column_kwargs={"unique": True})
    full_name: str
    hashed_password: str
    is_active: bool = Field(default=True)
    is_locked: bool = Field(default=False)
    super_admin: bool = Field(default=False)
    require_password_reset: bool = Field(default=False)
    password_reset_token: Optional[str] = None
    password_reset_requested_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrganizationMembership(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organization.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str = Field(default="member")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeatureFlag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, sa_column_kwargs={"unique": True})
    description: Optional[str] = None
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PlatformLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(default="system")
    level: str = Field(default="info")
    message: str
    details_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkerStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_type: str
    status: str = Field(default="idle")
    queue_depth: int = Field(default=0)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    details_json: str = Field(default="{}")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
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
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
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
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
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
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
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
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
    hostname: str
    triggered_by: str = Field(default="scheduler")
    status: str = Field(default="pending")
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scan_id: Optional[int] = Field(default=None, foreign_key="scan.id")
