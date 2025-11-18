from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BenchmarkMetadata(BaseModel):
    maintainer: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ExpectationDefinition(BaseModel):
    type: str
    value: str | int


class RuleCheckDefinition(BaseModel):
    type: str = Field(description="The type of check to execute (e.g. shell)")
    command: str
    timeout: int = 10
    expect: ExpectationDefinition


class RuleDefinition(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    remediation: str
    references: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    check: RuleCheckDefinition


class BenchmarkDocument(BaseModel):
    schema_version: str = Field(alias="schema_version")
    benchmark: "BenchmarkBlock"
    rules: List[RuleDefinition]


class BenchmarkBlock(BaseModel):
    id: str
    title: str
    description: str
    version: str
    os_target: str
    metadata: BenchmarkMetadata


class BenchmarkSummary(BaseModel):
    id: str
    title: str
    description: str
    version: str
    os_target: str
    maintainer: Optional[str] = None
    source: Optional[str] = None
    tags: List[str]
    total_rules: int
    updated_at: datetime


class RuleSummary(BaseModel):
    id: str
    benchmark_id: str
    title: str
    severity: str
    status: str = Field(default="active")
    tags: List[str] = Field(default_factory=list)
    last_run: Optional[datetime] = None


class RuleDetail(RuleSummary):
    description: str
    remediation: str
    references: List[str]
    metadata: Dict[str, Any]
    check_type: str
    command: str
    expect_type: str
    expect_value: str
    timeout_seconds: int


class BenchmarkDetail(BenchmarkSummary):
    description: str
    schema_version: str
