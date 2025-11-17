from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..auth.dependencies import require_authenticated_user
from ..models import Rule
from ..schemas import RuleDetail, RuleSummary
from .deps import get_db_session
from .benchmarks import _rule_to_detail, _rule_to_summary

router = APIRouter(
    prefix="/rules",
    tags=["rules"],
    dependencies=[Depends(require_authenticated_user)],
)


@router.get("", response_model=List[RuleSummary])
def list_rules(
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    benchmark_id: Optional[str] = Query(default=None, description="Filter by benchmark"),
    session: Session = Depends(get_db_session),
) -> List[RuleSummary]:
    statement = select(Rule)
    if severity:
        statement = statement.where(Rule.severity == severity)
    if benchmark_id:
        statement = statement.where(Rule.benchmark_id == benchmark_id)
    rules = session.exec(statement).all()
    return [_rule_to_summary(rule) for rule in rules]


@router.get("/{rule_id}", response_model=RuleDetail)
def get_rule(rule_id: str, session: Session = Depends(get_db_session)) -> RuleDetail:
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_to_detail(rule)
