from __future__ import annotations

from datetime import datetime
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


class Scan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hostname: str
    ip: Optional[str] = None
    benchmark_id: str = Field(foreign_key="benchmark.id")
    status: str = Field(default="pending")
    severity: str = Field(default="info")
    tags_json: str = Field(default="[]")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    total_rules: int = 0
    passed_rules: int = 0
    output_path: Optional[str] = None


class RuleResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id")
    rule_id: str = Field(foreign_key="rule.id")
    status: str = "pending"
    passed: bool = False
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    expectation_detail: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


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
