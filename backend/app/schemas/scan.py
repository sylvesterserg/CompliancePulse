from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    hostname: str
    ip: Optional[str] = None
    benchmark_id: str = Field(description="Benchmark identifier to execute")
    tags: List[str] = Field(default_factory=list)


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
    result: str
    severity: str
    started_at: datetime
    completed_at: Optional[datetime]
    last_run: Optional[datetime]
    total_rules: int
    passed_rules: int
    tags: List[str] = Field(default_factory=list)
    output_path: Optional[str] = None


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
    status: str
    severity: str
    tags: List[str] = Field(default_factory=list)
    output_path: Optional[str] = None
    last_run: Optional[datetime]
    created_at: datetime
