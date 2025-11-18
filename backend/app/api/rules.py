from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
import json
from sqlmodel import Session, select

from ..auth.dependencies import require_authenticated_user, verify_csrf_token
from ..models import Rule, Benchmark
from ..schemas import RuleDetail, RuleSummary
from .deps import get_db_session
from .benchmarks import _rule_to_detail, _rule_to_summary
from . import ui_router as _ui

router = APIRouter(
    prefix="/rules",
    tags=["rules"],
    dependencies=[Depends(require_authenticated_user)],
)


ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    if request.headers.get("hx-request") == "true":
        return True
    return "text/html" in accept and "application/json" not in accept


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


@router.get("/modal/new", response_class=HTMLResponse)
def new_rule_modal(request: Request, session: Session = Depends(get_db_session)) -> HTMLResponse:
    context_tuple = _ui._resolve_ui_context(request, session)
    if not context_tuple:
        # mirror UI behavior
        raise HTTPException(status_code=401, detail="unauthorized")
    context = {
        "request": request,
        "benchmarks": session.exec(select(Benchmark).order_by(Benchmark.title)).all(),
        "csrf_token": _ui._csrf_token(request),
    }
    return _ui._templates().TemplateResponse("modals/rule_new.html", context)


@router.get("/modal/edit/{rule_id}", response_class=HTMLResponse)
def edit_rule_modal(rule_id: str, request: Request, session: Session = Depends(get_db_session)) -> HTMLResponse:
    context_tuple = _ui._resolve_ui_context(request, session)
    if not context_tuple:
        raise HTTPException(status_code=401, detail="unauthorized")
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    context = {
        "request": request,
        "rule": rule,
        "benchmarks": session.exec(select(Benchmark).order_by(Benchmark.title)).all(),
        "csrf_token": _ui._csrf_token(request),
    }
    return _ui._templates().TemplateResponse("modals/rule_edit.html", context)


@router.get("/modal/delete/{rule_id}", response_class=HTMLResponse)
def delete_rule_modal(rule_id: str, request: Request, session: Session = Depends(get_db_session)) -> HTMLResponse:
    context_tuple = _ui._resolve_ui_context(request, session)
    if not context_tuple:
        raise HTTPException(status_code=401, detail="unauthorized")
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    context = {
        "request": request,
        "rule": rule,
        "csrf_token": _ui._csrf_token(request),
    }
    return _ui._templates().TemplateResponse("modals/rule_delete.html", context)


def _validate_rule_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    errors: Dict[str, str] = {}
    rid = str(data.get("rule_id") or data.get("id") or "").strip()
    benchmark_id = str(data.get("benchmark_id") or "").strip()
    title = str(data.get("title") or "").strip()
    severity = str(data.get("severity") or "low").strip().lower()
    command = str(data.get("command") or "").strip()
    expect_value = str(data.get("expect_value") or "0").strip() or "0"
    if not rid:
        errors["rule_id"] = "Rule ID is required"
    if not benchmark_id:
        errors["benchmark_id"] = "Benchmark is required"
    if not title:
        errors["title"] = "Title is required"
    if not command:
        errors["command"] = "Command is required"
    if severity not in ALLOWED_SEVERITIES:
        errors["severity"] = "Severity must be one of: low, medium, high, critical"
    return {
        "errors": errors,
        "payload": {
            "rule_id": rid,
            "benchmark_id": benchmark_id,
            "title": title,
            "severity": severity,
            "tags": str(data.get("tags") or ""),
            "description": str(data.get("description") or ""),
            "remediation": str(data.get("remediation") or ""),
            "command": command,
            "expect_value": expect_value,
        },
    }


@router.post("/create", response_class=HTMLResponse, dependencies=[Depends(verify_csrf_token)])
async def create_rule(request: Request, session: Session = Depends(get_db_session)):
    is_html = _wants_html(request)
    data: Dict[str, Any]
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)
    result = _validate_rule_payload(data)
    if result["errors"]:
        if is_html:
            context = {
                "request": request,
                "benchmarks": session.exec(select(Benchmark).order_by(Benchmark.title)).all(),
                "csrf_token": _ui._csrf_token(request),
                "error": next(iter(result["errors"].values())),
                "errors": result["errors"],
            }
            return _ui._templates().TemplateResponse("modals/rule_new.html", context, status_code=400)
        return JSONResponse({"errors": result["errors"]}, status_code=400)

    payload = result["payload"]
    rid = payload["rule_id"]
    if session.get(Rule, rid):
        message = "Rule ID already exists"
        if is_html:
            context = {
                "request": request,
                "benchmarks": session.exec(select(Benchmark).order_by(Benchmark.title)).all(),
                "csrf_token": _ui._csrf_token(request),
                "error": message,
            }
            return _ui._templates().TemplateResponse("modals/rule_new.html", context, status_code=400)
        return JSONResponse({"detail": message}, status_code=400)
    # Ensure benchmark exists
    if not session.get(Benchmark, payload["benchmark_id"]):
        msg = "Benchmark not found"
        if is_html:
            context = {
                "request": request,
                "benchmarks": session.exec(select(Benchmark).order_by(Benchmark.title)).all(),
                "csrf_token": _ui._csrf_token(request),
                "error": msg,
            }
            return _ui._templates().TemplateResponse("modals/rule_new.html", context, status_code=404)
        return JSONResponse({"detail": msg}, status_code=404)

    # Organization from UI context for now
    context_tuple = _ui._resolve_ui_context(request, session)
    if not context_tuple:
        raise HTTPException(status_code=401, detail="unauthorized")
    _, organization, _, _ = context_tuple

    tags = [t.strip() for t in payload["tags"].split(",") if t.strip()]
    rule = Rule(
        id=rid,
        organization_id=organization.id,
        benchmark_id=payload["benchmark_id"],
        title=payload["title"],
        description=payload["description"],
        severity=payload["severity"],
        remediation=payload["remediation"],
        references_json=json.dumps([]),
        metadata_json=json.dumps({"source": "ui"}),
        tags_json=json.dumps(tags),
        check_type="shell",
        command=payload["command"],
        expect_type="equals",
        expect_value=payload["expect_value"],
        timeout_seconds=10,
        status="active",
    )
    session.add(rule)
    session.commit()

    if is_html:
        return _ui._render_rules_table(request, session, modal_reset=True)
    payload = jsonable_encoder(_rule_to_detail(rule))
    return JSONResponse(payload, status_code=201, headers={"x-test-json-body": json.dumps(payload)})


@router.post("/{rule_id}/update", response_class=HTMLResponse, dependencies=[Depends(verify_csrf_token)])
async def update_rule(rule_id: str, request: Request, session: Session = Depends(get_db_session)):
    is_html = _wants_html(request)
    rule = session.get(Rule, rule_id)
    if not rule:
        if is_html:
            return HTMLResponse("Rule not found", status_code=404)
        raise HTTPException(status_code=404, detail="Rule not found")

    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)
    # Only validate changed fields but apply same constraints
    severity = str(data.get("severity", rule.severity)).strip().lower()
    if severity not in ALLOWED_SEVERITIES:
        msg = "Severity must be one of: low, medium, high, critical"
        if is_html:
            context = {
                "request": request,
                "rule": rule,
                "benchmarks": session.exec(select(Benchmark).order_by(Benchmark.title)).all(),
                "csrf_token": _ui._csrf_token(request),
                "error": msg,
            }
            return _ui._templates().TemplateResponse("modals/rule_edit.html", context, status_code=400)
        return JSONResponse({"detail": msg}, status_code=400)

    rule.title = str(data.get("title", rule.title)).strip() or rule.title
    rule.severity = severity
    rule.description = str(data.get("description", rule.description))
    rule.remediation = str(data.get("remediation", rule.remediation))
    rule.command = str(data.get("command", rule.command)).strip() or rule.command
    rule.expect_value = str(data.get("expect_value", rule.expect_value)).strip() or rule.expect_value
    rule.benchmark_id = str(data.get("benchmark_id", rule.benchmark_id)).strip() or rule.benchmark_id
    tags = str(data.get("tags", ",".join(json.loads(rule.tags_json or "[]"))))
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    rule.tags_json = json.dumps(tag_list)
    session.add(rule)
    session.commit()

    if is_html:
        return _ui._render_rules_table(request, session, modal_reset=True)
    payload = jsonable_encoder(_rule_to_detail(rule))
    return JSONResponse(payload, headers={"x-test-json-body": json.dumps(payload)})


@router.post("/{rule_id}/delete", response_class=HTMLResponse, dependencies=[Depends(verify_csrf_token)])
async def delete_rule(rule_id: str, request: Request, session: Session = Depends(get_db_session)):
    is_html = _wants_html(request)
    rule = session.get(Rule, rule_id)
    if not rule:
        if is_html:
            return HTMLResponse("Rule not found", status_code=404)
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    if is_html:
        return _ui._render_rules_table(request, session, modal_reset=True)
    payload = {"deleted": True, "id": rule_id}
    return JSONResponse(payload, headers={"x-test-json-body": json.dumps(payload)})
