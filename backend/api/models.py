"""Database models for CompliancePulse."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class System(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hostname: str = Field(index=True)
    ip: str | None = None
    os_version: str | None = None
    last_scan: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    system_id: int = Field(foreign_key="system.id")
    score: int = Field(ge=0, le=100)
    issues_json: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


__all__ = ["System", "Report"]
