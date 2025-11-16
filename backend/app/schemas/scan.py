from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    hostname: str
    ip: Optional[str] = None
    benchmark_id: str = Field(description="Benchmark identifier to execute")


class RuleResultView(BaseModel):
    id: int
    rule_id: str
    status: str
    passed: bool
    stdout: Optional[str]
    stderr: Optional[str]
    expectation_detail: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class ScanSummary(BaseModel):
    id: int
    hostname: str
    benchmark_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_rules: int
    passed_rules: int


class ScanDetail(ScanSummary):
    ip: Optional[str]
    results: List[RuleResultView]


class ReportView(BaseModel):
    id: int
    scan_id: int
    benchmark_id: str
    hostname: str
    score: float
    summary: str
    created_at: datetime
