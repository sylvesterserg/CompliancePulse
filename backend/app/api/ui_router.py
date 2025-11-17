from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from ..config import settings
from ..models import Benchmark, Report, Rule, RuleGroup, Scan, ScanJob, Schedule
from ..schemas import ScanRequest, ScheduleCreate
from ..services.scan_service import ScanService
from ..services.schedule_service import ScheduleService
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


def _rule_groups(session: Session) -> List[Dict[str, Any]]:
    groups = session.exec(select(RuleGroup).order_by(RuleGroup.created_at.desc())).all()
    data: List[Dict[str, Any]] = []
    for group in groups:
        next_schedule = (
            session.exec(
                select(Schedule)
                .where((Schedule.group_id == group.id) & (Schedule.enabled == True))  # noqa: E712
                .order_by(Schedule.next_run)
            )
            .first()
        )
        pending_jobs = session.exec(
            select(func.count(ScanJob.id)).where(
                (ScanJob.group_id == group.id) & (ScanJob.status == "pending")
            )
        ).one()
        data.append(
            {
                "id": group.id,
                "name": group.name,
                "benchmark_id": group.benchmark_id,
                "description": group.description,
                "default_hostname": group.default_hostname,
                "rule_count": len(json.loads(group.rule_ids_json or "[]")),
                "last_run": group.last_run,
                "next_run": next_schedule.next_run if next_schedule else None,
                "pending_jobs": pending_jobs,
                "tags": json.loads(group.tags_json or "[]"),
            }
        )
    return data


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


def _render_rule_groups_panel(
    request: Request,
    session: Session,
    message: str | None = None,
) -> HTMLResponse:
    context = {
        "request": request,
        "rule_groups": _rule_groups(session),
        "message": message,
    }
    return _templates().TemplateResponse("partials/rule_groups.html", context)


def _render_schedules_table(
    request: Request,
    schedule_service: ScheduleService,
    modal_reset: bool = False,
) -> HTMLResponse:
    context = {
        "request": request,
        "schedules": schedule_service.list_schedules(),
        "modal_reset": modal_reset,
    }
    return _templates().TemplateResponse("partials/schedules_table.html", context)


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
    schedule_service = ScheduleService(session)
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
        "rule_groups": _rule_groups(session),
        "schedules": schedule_service.list_schedules(),
        "next_schedule": schedule_service.get_next_schedule(),
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


@router.get("/automation/modal/schedule", response_class=HTMLResponse)
async def schedule_modal(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    schedule_service = ScheduleService(session)
    context = {"request": request, "rule_groups": schedule_service.list_rule_groups()}
    return _templates().TemplateResponse("modals/schedule_new.html", context)


@router.post("/automation/schedules", response_class=HTMLResponse)
async def create_schedule_from_modal(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    form = await request.form()
    name = str(form.get("name", "")).strip()
    group_id = int(form.get("group_id", 0))
    frequency = str(form.get("frequency", "daily")).strip() or "daily"
    interval = form.get("interval_minutes")
    interval_minutes = int(interval) if interval else None
    if not name or not group_id:
        raise HTTPException(status_code=400, detail="Name and group are required")
    schedule_service = ScheduleService(session)
    payload = ScheduleCreate(
        name=name,
        group_id=group_id,
        frequency=frequency,
        interval_minutes=interval_minutes,
        enabled=True,
    )
    try:
        schedule_service.create_schedule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _render_schedules_table(request, schedule_service, modal_reset=True)


@router.delete("/automation/schedules/{schedule_id}", response_class=HTMLResponse)
async def delete_schedule_from_dashboard(
    schedule_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    schedule_service = ScheduleService(session)
    try:
        schedule_service.delete_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _render_schedules_table(request, schedule_service)


@router.post("/automation/groups/{group_id}/run", response_class=HTMLResponse)
async def run_group_now(
    group_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    scan_service = ScanService(session)
    try:
        job = scan_service.enqueue_group_scan(group_id, triggered_by="ui")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    group = session.get(RuleGroup, group_id)
    message = f"Queued scan for {group.name if group else 'group'}"
    return _render_rule_groups_panel(request, session, message=message)


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
