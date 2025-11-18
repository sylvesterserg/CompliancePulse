from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class MembershipRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, sa_column_kwargs={"unique": True})
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, sa_column_kwargs={"unique": True})
    hashed_password: str
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserOrganization(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    organization_id: int = Field(foreign_key="organization.id", primary_key=True)
    role: MembershipRole = Field(default=MembershipRole.MEMBER)
    joined_at: datetime = Field(default_factory=datetime.utcnow)


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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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
    organization_id: int = Field(foreign_key="organization.id", index=True)
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


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    organization_id: Optional[str] = Field(default=None, index=True)
    action_type: str = Field(index=True)
    resource_type: Optional[str] = Field(default=None, index=True)
    resource_id: Optional[str] = Field(default=None)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata_json: str = Field(default="{}", sa_column=Column(Text))


class ApiKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: Optional[str] = Field(default=None, index=True)
    name: str
    hashed_key: str = Field(sa_column=Column(Text, nullable=False))
    prefix: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    is_active: bool = Field(default=True, index=True)
    scopes_json: str = Field(default="", sa_column=Column(Text))

    @property
    def scopes(self) -> List[str]:
        if not self.scopes_json:
            return []
        return [scope for scope in self.scopes_json.split(",") if scope]
