from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import List, Sequence

from fastapi import Depends, Header, HTTPException, Request, status
from sqlmodel import Session, select

from ..database import get_session
from ..models import ApiKey
from ..schemas.security import ApiKeyView
from .audit import log_action
from .config import security_settings
from .rate_limit import enforce_api_key_limit
from .utils import mask_secret

API_KEY_HEADER = "x-api-key"


class ApiKeyManager:
    def __init__(self, session: Session):
        self.session = session

    def list_keys(self) -> List[ApiKeyView]:
        keys = self.session.exec(select(ApiKey).order_by(ApiKey.created_at.desc())).all()
        return [ApiKeyView.from_orm(key) for key in keys]

    def create_key(
        self,
        *,
        organization_id: str | None,
        name: str,
        scopes: Sequence[str] | None = None,
    ) -> tuple[str, ApiKey]:
        raw_key = secrets.token_urlsafe(48)
        hashed_key = _hash_api_key(raw_key)
        prefix = raw_key[:12]
        record = ApiKey(
            organization_id=organization_id,
            name=name,
            hashed_key=hashed_key,
            prefix=prefix,
            scopes_json=_encode_scopes(scopes or []),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        log_action(
            action_type="API_KEY_CREATE",
            resource_type="API_KEY",
            resource_id=record.id,
            request=None,
            user=None,
            org=None,
            metadata={"name": name, "prefix": prefix},
        )
        return raw_key, record

    def revoke_key(self, key_id: int) -> ApiKey:
        key = self.session.get(ApiKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")
        key.is_active = False
        self.session.add(key)
        self.session.commit()
        log_action(
            action_type="API_KEY_REVOKE",
            resource_type="API_KEY",
            resource_id=key.id,
            request=None,
            user=None,
            org=None,
            metadata={"prefix": key.prefix},
        )
        return key


def _hash_api_key(raw_key: str) -> str:
    digest = hmac.new(
        key=security_settings.api_key_hash_salt.encode("utf-8"),
        msg=raw_key.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return digest


def _encode_scopes(scopes: Sequence[str]) -> str:
    return ",".join(sorted(set(scopes)))


def _decode_scopes(scopes: str | None) -> List[str]:
    if not scopes:
        return []
    return [scope for scope in scopes.split(",") if scope]


def verify_api_key(session: Session, raw_key: str) -> ApiKey | None:
    prefix = raw_key[:12]
    hashed = _hash_api_key(raw_key)
    statement = select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.is_active == True)  # noqa: E712
    candidate = session.exec(statement).first()
    if not candidate:
        return None
    if not hmac.compare_digest(candidate.hashed_key, hashed):
        return None
    candidate.last_used_at = datetime.utcnow()
    session.add(candidate)
    session.commit()
    enforce_api_key_limit(candidate.prefix)
    log_action(
        action_type="API_KEY_USAGE",
        resource_type="API_KEY",
        resource_id=candidate.id,
        request=None,
        user=None,
        org=None,
        metadata={"prefix": mask_secret(candidate.prefix)},
    )
    return candidate


def get_api_key_from_request(
    request: Request,
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
    api_key_header: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> ApiKey:
    token = _extract_api_key(authorization, api_key_header)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    record = verify_api_key(session, token)
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return record


def get_optional_api_key(
    request: Request,
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
    api_key_header: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> ApiKey | None:
    token = _extract_api_key(authorization, api_key_header)
    if not token:
        return None
    record = verify_api_key(session, token)
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return record


def _extract_api_key(authorization: str | None, api_key_header: str | None) -> str | None:
    if api_key_header:
        return api_key_header.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None
