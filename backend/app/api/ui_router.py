from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from ..config import settings
from ..models import Benchmark, Report, Rule, Scan
from ..schemas import ScanRequest
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter()

_templates_instance: Jinja2Templates | None = None


def _templates() -> Jinja2Templates:
    global _templates_instance
    if _templates_instance is None:
        _templates_instance = Jinja2Templates(directory=str(settings.frontend_template_dir))
        _templates_instance.env.globals.update({"app_name": settings.app_name})
    return _templates_instance


def _base_context(request: Request, session: Session, active: str) -> Dict[str, Any]:
    return {
        "request": request,
        "environment": settings.environment,
        "nav_active": active,
        "health_status": _health_status(session),
        "page_title": active.title(),
    }


def _health_status(session: Session) -> Dict[str, str]:
    try:
        session.exec(select(func.count(Rule.id)).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception:  # pragma: no cover - defensive
        return {"status": "degraded", "database": "unreachable"}


def _serialize_rule(rule: Rule) -> Dict[str, Any]:
    return {
        "id": rule.id,
        "benchmark_id": rule.benchmark_id,
        "title": rule.title,
        "severity": rule.severity,
        "status": rule.status,
        "tags": json.loads(rule.tags_json or "[]"),
        "last_run": rule.last_run,
    }


def _rule_list(session: Session) -> List[Dict[str, Any]]:
    rules = session.exec(select(Rule).order_by(Rule.created_at.desc())).all()
    return [_serialize_rule(rule) for rule in rules]


def _benchmarks(session: Session) -> List[Benchmark]:
    return session.exec(select(Benchmark).order_by(Benchmark.title)).all()


def _render_rules_table(request: Request, session: Session, modal_reset: bool = False) -> HTMLResponse:
    context = {"request": request, "rules": _rule_list(session), "modal_reset": modal_reset}
    return _templates().TemplateResponse("partials/rules_table.html", context)


def _render_scans_table(request: Request, scan_service: ScanService, modal_reset: bool = False) -> HTMLResponse:
    context = {
        "request": request,
        "scans": scan_service.list_scans(),
        "modal_reset": modal_reset,
    }
    return _templates().TemplateResponse("partials/scans_table.html", context)


def _render_reports_table(request: Request, scan_service: ScanService) -> HTMLResponse:
    context = {
        "request": request,
        "reports": scan_service.list_reports(),
    }
    return _templates().TemplateResponse("partials/reports_table.html", context)


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    scan_service = ScanService(session)
    scans = scan_service.list_scans()
    reports = scan_service.list_reports()
    failed_scans = [scan for scan in scans if scan.result == "failed"][:5]
    compliance_score = 0.0
    if reports:
        compliance_score = round(sum(report.score for report in reports) / len(reports), 2)
    context = {
        **_base_context(request, session, "dashboard"),
        "rules_count": session.exec(select(func.count(Rule.id))).one(),
        "scans_count": session.exec(select(func.count(Scan.id))).one(),
        "last_failed_scans": failed_scans,
        "compliance_score": compliance_score,
        "recent_reports": reports[:4],
    }
    return _templates().TemplateResponse("dashboard.html", context)


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    context = {
        **_base_context(request, session, "rules"),
        "rules": _rule_list(session),
        "modal_reset": False,
    }
    return _templates().TemplateResponse("rules.html", context)


@router.get("/scans", response_class=HTMLResponse)
async def scans_page(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    scan_service = ScanService(session)
    context = {
        **_base_context(request, session, "scans"),
        "scans": scan_service.list_scans(),
    }
    return _templates().TemplateResponse("scans.html", context)


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    scan_service = ScanService(session)
    context = {
        **_base_context(request, session, "reports"),
        "reports": scan_service.list_reports(),
    }
    return _templates().TemplateResponse("reports.html", context)


@router.get("/rules/modal/new", response_class=HTMLResponse)
async def rule_modal(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    context = {"request": request, "benchmarks": _benchmarks(session)}
    return _templates().TemplateResponse("modals/rule_new.html", context)


@router.post("/rules/create", response_class=HTMLResponse)
async def create_rule(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    form = await request.form()
    rule_id = str(form.get("rule_id", "")).strip()
    benchmark_id = str(form.get("benchmark_id", "")).strip()
    title = str(form.get("title", "")).strip()
    severity = str(form.get("severity", "low")).strip() or "low"
    tags = str(form.get("tags", ""))
    description = str(form.get("description", ""))
    remediation = str(form.get("remediation", ""))
    command = str(form.get("command", "")).strip()
    expect_value = str(form.get("expect_value", "0")).strip() or "0"
    if not rule_id or not benchmark_id or not title or not command:
        raise HTTPException(status_code=400, detail="Missing required fields")
    existing = session.get(Rule, rule_id)
    if existing:
        raise HTTPException(status_code=400, detail="Rule ID already exists")
    benchmark = session.get(Benchmark, benchmark_id)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    rule = Rule(
        id=rule_id,
        benchmark_id=benchmark_id,
        title=title,
        description=description or "",
        severity=severity,
        remediation=remediation or "",
        references_json=json.dumps([]),
        metadata_json=json.dumps({"source": "ui"}),
        tags_json=json.dumps(tag_list),
        check_type="shell",
        command=command,
        expect_type="equals",
        expect_value=expect_value,
        timeout_seconds=10,
        status="active",
    )
    session.add(rule)
    session.commit()
    return _render_rules_table(request, session, modal_reset=True)


@router.get("/scans/modal/trigger", response_class=HTMLResponse)
async def scan_modal(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    context = {"request": request, "benchmarks": _benchmarks(session)}
    return _templates().TemplateResponse("modals/scan_trigger.html", context)


@router.post("/scans/trigger", response_class=HTMLResponse)
async def trigger_scan(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    form = await request.form()
    hostname = str(form.get("hostname", "")).strip()
    ip = str(form.get("ip", "")).strip()
    benchmark_id = str(form.get("benchmark_id", "")).strip()
    tags = str(form.get("tags", ""))
    if not hostname or not benchmark_id:
        raise HTTPException(status_code=400, detail="Missing required fields")
    scan_service = ScanService(session)
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    payload = ScanRequest(hostname=hostname, ip=ip or None, benchmark_id=benchmark_id, tags=tag_list)
    scan_service.start_scan(payload)
    return _render_scans_table(request, scan_service, modal_reset=True)


@router.get("/reports/{report_id}/view", response_class=HTMLResponse)
async def report_modal(
    report_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    scan_service = ScanService(session)
    try:
        report = scan_service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    context = {"request": request, "report": report}
    return _templates().TemplateResponse("modals/report_view.html", context)
