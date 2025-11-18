from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Sequence, Type

from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria
from sqlmodel import Session, SQLModel, create_engine

from .config import settings
from .models import Report, Rule, RuleGroup, Scan, ScanJob, ScanResult, Schedule

engine = create_engine(settings.database_url, echo=False)

TENANT_AWARE_MODELS: Sequence[Type[SQLModel]] = (
    Rule,
    RuleGroup,
    Scan,
    ScanResult,
    Report,
    Schedule,
    ScanJob,
)


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state) -> None:  # pragma: no cover - SQLAlchemy hook
    session = execute_state.session
    organization_id = session.info.get("organization_id")
    if not organization_id or not execute_state.is_select:
        return
    org_id = organization_id
    def _criteria(cls):
        return cls.organization_id == org_id

    for model in TENANT_AWARE_MODELS:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                model,
                _criteria,
                include_aliases=True,
            )
        )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
