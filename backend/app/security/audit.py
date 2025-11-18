from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import Request
from sqlmodel import Session, select

from ..database import engine
from ..models import AuditLog
from .utils import get_client_context, json_dumps, sanitize_metadata

logger = logging.getLogger("compliancepulse.audit")


def log_action(
    *,
    action_type: str,
    resource_type: str | None,
    resource_id: str | int | None,
    request: Request | None,
    user: Any | None,
    org: Any | None,
    metadata: Dict[str, Any] | None = None,
) -> None:
    metadata = sanitize_metadata(metadata)
    ip_address, user_agent = get_client_context(request)
    payload = AuditLog(
        timestamp=datetime.utcnow(),
        user_id=getattr(user, "id", None) if user else None,
        organization_id=getattr(org, "id", None) if org else None,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=json_dumps(metadata),
    )
    session = Session(engine)
    try:
        session.add(payload)
        session.commit()
    except Exception as exc:  # pragma: no cover - fail open
        session.rollback()
        logger.exception("Failed to persist audit log: %s", exc)
    finally:
        session.close()


def get_recent_audit_logs(limit: int = 50) -> List[AuditLog]:
    session = Session(engine)
    try:
        statement = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        return list(session.exec(statement).all())
    finally:
        session.close()
