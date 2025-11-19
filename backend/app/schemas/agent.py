from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    uuid: Optional[str] = None
    hostname: str
    os: str
    version: str
    ip: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class AgentRegisterResponse(BaseModel):
    agent_id: int
    uuid: str
    token: str
    expires_at: datetime


class AgentAuthRequest(BaseModel):
    uuid: str
    hostname: str
    os: Optional[str] = None
    version: Optional[str] = None


class AgentAuthResponse(BaseModel):
    token: str
    expires_at: datetime


class AgentHeartbeatRequest(BaseModel):
    ip: Optional[str] = None
    version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class AgentJobPayload(BaseModel):
    id: int
    benchmark_id: str
    rules: List[Dict[str, Any]] = Field(default_factory=list)


class AgentResultUpload(BaseModel):
    status: str = Field(default="completed")
    score: Optional[float] = None
    results: List[Dict[str, Any]]

