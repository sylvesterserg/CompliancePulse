from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from starlette.responses import Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from ..auth.dependencies import verify_csrf_token
from ..config import settings
from ..security.config import security_settings
from ..database import get_session
from ..models import (
    Benchmark,
    MembershipRole,
    Organization,
    Report,
    Rule,
    RuleGroup,
    Scan,
    ScanJob,
    Schedule,
    User,
    UserOrganization,
)
from ..schemas import ScanRequest, ScheduleCreate
from ..services.scan_service import ScanService
from ..services.schedule_service import ScheduleService

router = APIRouter()

def _json_payload(payload: Dict[str, Any], status_code: int | None = None) -> JSONResponse:
    as_text = json.dumps(payload)
    if security_settings.security_test_mode:
        return PlainTextResponse(
            as_text,
            media_type="application/json",
            status_code=status_code or 200,
            headers={"x-test-json-body": as_text},
        )
    return JSONResponse(payload, status_code=status_code or 200, headers={"x-test-json-body": as_text})

_templates_instance: Jinja2Templates | None = None


def _templates() -> Jinja2Templates:
    global _templates_instance
    if _templates_instance is None:
        _templates_instance = Jinja2Templates(directory=str(settings.frontend_template_dir))
        _templates_instance.env.globals.update({"app_name": settings.app_name})
    return _templates_instance


def _health_status(session: Session) -> Dict[str, str]:
    try:
        session.exec(select(func.count(Rule.id)).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception:  # pragma: no cover - defensive
        return {"status": "degraded", "database": "unreachable"}


def _resolve_ui_context(
    request: Request, session: Session
) -> Optional[Tuple[User, Organization, List[Organization], UserOrganization]]:
    # Test-mode header auth to mirror API deps
    if security_settings.security_test_mode:
        test_user = request.headers.get("x-test-user")
        test_org = request.headers.get("x-test-org")
        if test_user:
            try:
                user_id = int(test_user)
            except ValueError:
                user_id = None
            org_id = None
            if test_org:
                try:
                    org_id = int(test_org)
                except ValueError:
                    org_id = None
            from ..auth.utils import SessionData as _SD  # local import
            from datetime import datetime, timedelta

            request.state.session_data = _SD(
                user_id=user_id,
                organization_id=org_id,
                csrf_token="test",
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
    session_data = getattr(request.state, "session_data", None)
    if not session_data or not session_data.user_id:
        return None
    user = session.get(User, session_data.user_id)
    if not user or not user.is_active:
        return None
    memberships = session.exec(
        select(UserOrganization).where(UserOrganization.user_id == user.id)
    ).all()
    if not memberships:
        return None
    current_org_id = session_data.organization_id or memberships[0].organization_id
    organization = session.get(Organization, current_org_id)
    if not organization:
        organization = session.get(Organization, memberships[0].organization_id)
        if not organization:
            return None
        current_org_id = organization.id
    session_data.organization_id = current_org_id
    request.state.session_data = session_data
    request.state.session_dirty = True
    session.info["organization_id"] = organization.id
    membership = next(
        (m for m in memberships if m.organization_id == organization.id), memberships[0]
    )
    organizations: List[Organization] = []
    for member in memberships:
        org = session.get(Organization, member.organization_id)
        if org:
            organizations.append(org)
    request.state.current_user = user
    request.state.current_organization = organization
    request.state.current_membership = membership
    return user, organization, organizations, membership


def _redirect_to_login() -> RedirectResponse:
    # JSON fallback for unauthenticated calls to UI routes
    def _json_unauthorized() -> Response:
        return _json_payload({"error": "unauthorized", "status": 401}, status_code=401)

    # If the caller prefers JSON (e.g., tests or API usage), return JSON 401
    try:
        from fastapi import Request as _Req  # type: ignore
    except Exception:  # pragma: no cover - defensive
        pass

    # Starlette doesn't pass request here, so rely on global header inspection via context not available.
    # Callers that want JSON should use the helper exposed by handlers below.
    return RedirectResponse("/auth/login", status_code=303)


def _wants_json(request: Request) -> bool:
    """Only emit JSON for UI routes when explicitly requested.

    Many browsers/extensions include application/json in Accept. Prefer HTML
    if text/html is present. Allow tests to force JSON via X-Test-Json header.
    """
    accept = (request.headers.get("accept") or "").lower()
    if request.headers.get("x-test-json") == "1":
        return True
    if "text/html" in accept:
        return False
    return "application/json" in accept


def _base_context(
    request: Request,
    session: Session,
    active: str,
    user: User,
    organization: Organization,
    organizations: List[Organization],
    membership: UserOrganization,
) -> Dict[str, Any]:
    return {
        "request": request,
        "environment": settings.environment,
        "nav_active": active,
        "health_status": _health_status(session),
        "page_title": active.title(),
        "current_user": user,
        "current_organization": organization,
        "organizations": organizations,
        "membership": membership,
        "csrf_token": _csrf_token(request),
    }


def _csrf_token(request: Request) -> str:
    session_data = getattr(request.state, "session_data", None)
    return session_data.csrf_token if session_data else ""


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
    context = {
        "request": request,
        "rules": _rule_list(session),
        "modal_reset": modal_reset,
        "csrf_token": _csrf_token(request),
    }
    return _templates().TemplateResponse("partials/rules_table.html", context)


def _render_scans_table(
    request: Request,
    scan_service: ScanService,
    modal_reset: bool = False,
) -> HTMLResponse:
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
        "csrf_token": _csrf_token(request),
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
        "csrf_token": _csrf_token(request),
    }
    return _templates().TemplateResponse("partials/schedules_table.html", context)


def _render_reports_table(request: Request, scan_service: ScanService) -> HTMLResponse:
    context = {
        "request": request,
        "reports": scan_service.list_reports(),
    }
    return _templates().TemplateResponse("partials/reports_table.html", context)


def _ensure_admin(membership: UserOrganization) -> None:
    allowed = {MembershipRole.ADMIN, MembershipRole.OWNER}
    if membership.role not in allowed:
        raise HTTPException(status_code=403, detail="Administrator role required")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        if _wants_json(request):
            return _json_payload({"error": "unauthorized", "status": 401}, status_code=401)
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    scan_service = ScanService(session, organization.id)
    schedule_service = ScheduleService(session, organization.id)
    scans = scan_service.list_scans()
    reports = scan_service.list_reports()
    failed_scans = [scan for scan in scans if scan.result == "failed"][:5]
    compliance_score = 0.0
    if reports:
        compliance_score = round(sum(report.score for report in reports) / len(reports), 2)
    context = {
        **_base_context(request, session, "dashboard", user, organization, organizations, membership),
        "rules_count": session.exec(select(func.count(Rule.id))).one(),
        "scans_count": session.exec(select(func.count(Scan.id))).one(),
        "last_failed_scans": failed_scans,
        "compliance_score": compliance_score,
        "recent_reports": reports[:4],
        "rule_groups": _rule_groups(session),
        "schedules": schedule_service.list_schedules(),
        "next_schedule": schedule_service.get_next_schedule(),
    }
    if _wants_json(request):
        return _json_payload({
            "page": "dashboard",
            "health_status": context["health_status"],
            "rules_count": context["rules_count"],
            "scans_count": context["scans_count"],
            "compliance_score": context["compliance_score"],
        })
    return _templates().TemplateResponse("dashboard.html", context)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    # Serve the same dashboard content at /dashboard for UX/tests
    return await dashboard(request, session)  # type: ignore[arg-type]


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        if _wants_json(request):
            return _json_payload({"error": "unauthorized", "status": 401}, status_code=401)
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    context = {
        **_base_context(request, session, "rules", user, organization, organizations, membership),
        "rules": _rule_list(session),
        "modal_reset": False,
    }
    if _wants_json(request):
        return _json_payload({"page": "rules", "count": len(context["rules"])})
    return _templates().TemplateResponse("rules.html", context)


@router.get("/scans", response_class=HTMLResponse)
async def scans_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        if _wants_json(request):
            return _json_payload({"error": "unauthorized", "status": 401}, status_code=401)
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    scan_service = ScanService(session, organization.id)
    context = {
        **_base_context(request, session, "scans", user, organization, organizations, membership),
        "scans": scan_service.list_scans(),
    }
    if _wants_json(request):
        return _json_payload({"page": "scans", "count": len(context["scans"])})
    return _templates().TemplateResponse("scans.html", context)


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        if _wants_json(request):
            return _json_payload({"error": "unauthorized", "status": 401}, status_code=401)
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    scan_service = ScanService(session, organization.id)
    context = {
        **_base_context(request, session, "reports", user, organization, organizations, membership),
        "reports": scan_service.list_reports(),
    }
    if _wants_json(request):
        return _json_payload({"page": "reports", "count": len(context["reports"])})
    return _templates().TemplateResponse("reports.html", context)


@router.get("/rules/modal/new", response_class=HTMLResponse)
async def rule_modal(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    context = {
        "request": request,
        "benchmarks": _benchmarks(session),
        "csrf_token": _csrf_token(request),
    }
    return _templates().TemplateResponse("modals/rule_new.html", context)


@router.post(
    "/rules/create",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token)],
)
async def create_rule(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
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
        organization_id=organization.id,
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
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    context = {
        "request": request,
        "benchmarks": _benchmarks(session),
        "csrf_token": _csrf_token(request),
    }
    return _templates().TemplateResponse("modals/scan_trigger.html", context)


@router.post(
    "/scans/trigger",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token)],
)
async def trigger_scan(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    form = await request.form()
    hostname = str(form.get("hostname", "")).strip()
    ip = str(form.get("ip", "")).strip()
    benchmark_id = str(form.get("benchmark_id", "")).strip()
    tags = str(form.get("tags", ""))
    if not hostname or not benchmark_id:
        raise HTTPException(status_code=400, detail="Missing required fields")
    scan_service = ScanService(session, organization.id)
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    payload = ScanRequest(hostname=hostname, ip=ip or None, benchmark_id=benchmark_id, tags=tag_list)
    scan_service.start_scan(payload)
    return _render_scans_table(request, scan_service, modal_reset=True)


@router.get("/automation/modal/schedule", response_class=HTMLResponse)
async def schedule_modal(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    schedule_service = ScheduleService(session, organization.id)
    context = {
        "request": request,
        "rule_groups": schedule_service.list_rule_groups(),
        "csrf_token": _csrf_token(request),
    }
    return _templates().TemplateResponse("modals/schedule_new.html", context)


@router.post(
    "/automation/schedules",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token)],
)
async def create_schedule_from_modal(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    group_id = int(form.get("group_id", 0))
    frequency = str(form.get("frequency", "daily")).strip() or "daily"
    interval = form.get("interval_minutes")
    interval_minutes = int(interval) if interval else None
    if not name or not group_id:
        raise HTTPException(status_code=400, detail="Name and group are required")
    schedule_service = ScheduleService(session, organization.id)
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


@router.delete(
    "/automation/schedules/{schedule_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token)],
)
async def delete_schedule_from_dashboard(
    schedule_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    schedule_service = ScheduleService(session, organization.id)
    try:
        schedule_service.delete_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _render_schedules_table(request, schedule_service)


@router.post(
    "/automation/groups/{group_id}/run",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token)],
)
async def run_group_now(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    _ensure_admin(membership)
    scan_service = ScanService(session, organization.id)
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
    session: Session = Depends(get_session),
) -> Response:
    context_tuple = _resolve_ui_context(request, session)
    if not context_tuple:
        return _redirect_to_login()
    user, organization, organizations, membership = context_tuple
    scan_service = ScanService(session, organization.id)
    try:
        report = scan_service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    context = {"request": request, "report": report}
    return _templates().TemplateResponse("modals/report_view.html", context)
