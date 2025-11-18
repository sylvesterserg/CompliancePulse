from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json
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


@router.get("")
def list_rules(
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    benchmark_id: Optional[str] = Query(default=None, description="Filter by benchmark"),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    statement = select(Rule)
    if severity:
        statement = statement.where(Rule.severity == severity)
    if benchmark_id:
        statement = statement.where(Rule.benchmark_id == benchmark_id)
    rules = session.exec(statement).all()
    payload = {"page": "rules", "count": len(rules)}
    import json as _json
    return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})


@router.get("/{rule_id}")
def get_rule(rule_id: str, session: Session = Depends(get_db_session)) -> JSONResponse:
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    payload = jsonable_encoder(_rule_to_detail(rule))
    return JSONResponse(payload, headers={"x-test-json-body": json.dumps(payload)})
