from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

from pydantic import BaseModel, Field

from ..security.utils import mask_secret


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., description="Human readable label")
    organization_id: str | None = Field(default=None)
    scopes: Sequence[str] | None = Field(default=None)


class ApiKeyView(BaseModel):
    id: int
    organization_id: str | None = None
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool
    scopes: List[str] = Field(default_factory=list)

    @classmethod
    def from_orm(cls, obj: "ApiKey") -> "ApiKeyView":  # type: ignore[name-defined]
        from ..models import ApiKey  # Local import to avoid circular

        if not isinstance(obj, ApiKey):  # pragma: no cover - defensive
            raise TypeError("Expected ApiKey instance")
        return cls(
            id=obj.id,
            organization_id=obj.organization_id,
            name=obj.name,
            prefix=obj.prefix,
            created_at=obj.created_at,
            last_used_at=obj.last_used_at,
            is_active=obj.is_active,
            scopes=obj.scopes,
        )


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    prefix: str
    api_key: str
    masked_key: str

    @classmethod
    def from_pair(cls, api_key: str, record: "ApiKey") -> "ApiKeyCreateResponse":  # type: ignore[name-defined]
        from ..models import ApiKey

        if not isinstance(record, ApiKey):  # pragma: no cover
            raise TypeError("Expected ApiKey instance")
        return cls(
            id=record.id,
            name=record.name,
            prefix=record.prefix,
            api_key=api_key,
            masked_key=mask_secret(api_key),
        )
