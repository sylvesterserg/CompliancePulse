from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RuleGroupView(BaseModel):
    id: int
    name: str
    benchmark_id: str
    description: Optional[str]
    default_hostname: str
    default_ip: Optional[str]
    tags: List[str] = Field(default_factory=list)
    rule_count: int
    last_run: Optional[datetime]


class ScheduleCreate(BaseModel):
    name: str
    group_id: int
    frequency: str = Field(pattern="^(hourly|daily|custom)$")
    interval_minutes: Optional[int] = None
    enabled: bool = True


class ScheduleView(BaseModel):
    id: int
    name: str
    group_id: int
    group_name: str
    frequency: str
    interval_minutes: int
    enabled: bool
    next_run: Optional[datetime]
    last_run: Optional[datetime]
    timezone: str
