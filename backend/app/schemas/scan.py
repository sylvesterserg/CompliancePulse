from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    hostname: str
    ip: Optional[str] = None
    benchmark_id: str = Field(description="Benchmark identifier to execute")
    tags: List[str] = Field(default_factory=list)


class ScanResultView(BaseModel):
    id: int
    rule_id: str
    rule_title: str
    severity: str
    status: str
    passed: bool
    stdout: Optional[str]
    stderr: Optional[str]
    details: Dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime
    completed_at: Optional[datetime]
    runtime_ms: Optional[int]


class ScanSummary(BaseModel):
    id: int
    hostname: str
    benchmark_id: str
    group_id: Optional[int]
    status: str
    result: str
    severity: str
    started_at: datetime
    completed_at: Optional[datetime]
    last_run: Optional[datetime]
    total_rules: int
    passed_rules: int
    compliance_score: float
    summary: Optional[str]
    triggered_by: str
    tags: List[str] = Field(default_factory=list)
    output_path: Optional[str] = None


class ScanDetail(ScanSummary):
    ip: Optional[str]
    results: List[ScanResultView]
    ai_summary: Dict[str, Any] = Field(default_factory=dict)


class ScanJobView(BaseModel):
    id: int
    group_id: int
    hostname: str
    schedule_id: Optional[int]
    triggered_by: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class ReportView(BaseModel):
    id: int
    scan_id: int
    benchmark_id: str
    hostname: str
    score: float
    summary: str
    key_findings: List[str] = Field(default_factory=list)
    remediations: List[str] = Field(default_factory=list)
    status: str = "generated"
    severity: str = "info"
    tags: List[str] = Field(default_factory=list)
    output_path: Optional[str] = None
    last_run: Optional[datetime] = None
    created_at: datetime
