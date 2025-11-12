"""Shared dependencies and utilities for the CompliancePulse API."""
from __future__ import annotations

import json
import os
from typing import Any, Iterator

from sqlmodel import Session, create_engine

DB_URL = os.getenv("DB_URL", "sqlite:////app/data/compliancepulse.db")

# Central engine used across the application.
engine = create_engine(DB_URL, echo=False)


def get_session() -> Iterator[Session]:
    """Yield a database session with consistent configuration."""
    with Session(engine, expire_on_commit=False) as session:
        yield session


# Centralised JSON helpers avoid re-importing json inside hot paths.
def json_dumps(data: Any, *, ensure_ascii: bool = False) -> str:
    return json.dumps(data, ensure_ascii=ensure_ascii)


def json_loads(data: str) -> Any:
    return json.loads(data)


__all__ = ["engine", "get_session", "json_dumps", "json_loads"]
