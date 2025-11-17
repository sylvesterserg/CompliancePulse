from __future__ import annotations

from datetime import datetime
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from ..api.deps import get_db_session
from ..models import Organization, PlatformLog, RuleGroup, ScanJob, User
from ..services.scan_service import ScanService
from engine.scan_executor import ScanExecutor
from . import analytics, flags, system
from .dependencies import admin_base_context, get_admin_templates, require_super_admin

router = APIRouter(prefix="/admin", tags=["Super Admin"])
templates = get_admin_templates()


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def admin_index(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    dashboard = analytics.dashboard_metrics(session)
    context = {**admin_base_context(request, "overview", session, current_user), **dashboard}
    return templates.TemplateResponse("admin/index.html", context)


@router.get("/orgs", response_class=HTMLResponse)
def admin_orgs(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    organizations = analytics.list_organizations(session)
    context = {
        **admin_base_context(request, "orgs", session, current_user),
        "organizations": organizations,
        "plan_options": ["starter", "team", "enterprise"],
    }
    return templates.TemplateResponse("admin/orgs.html", context)


@router.post("/orgs/{org_id}/suspend")
def suspend_org(
    org_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization.is_active = False
    organization.suspended_at = datetime.utcnow()
    session.add(organization)
    session.commit()
    return RedirectResponse(url="/admin/orgs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/orgs/{org_id}/activate")
def activate_org(
    org_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization.is_active = True
    organization.suspended_at = None
    session.add(organization)
    session.commit()
    return RedirectResponse(url="/admin/orgs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/orgs/{org_id}/change-plan")
def change_org_plan(
    org_id: int,
    plan: str = Form(...),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization.plan_tier = plan
    session.add(organization)
    session.commit()
    return RedirectResponse(url="/admin/orgs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/orgs/{org_id}/force-scan")
def force_scan(
    org_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    group = (
        session.exec(select(RuleGroup).where(RuleGroup.organization_id == org_id).order_by(RuleGroup.created_at)).first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No rule groups to scan for organization")
    executor = ScanExecutor(session)
    executor.run_for_group(group_id=group.id, triggered_by="super-admin")
    return RedirectResponse(url="/admin/scans", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    users = analytics.list_users(session)
    context = {**admin_base_context(request, "users", session, current_user), "users": users}
    return templates.TemplateResponse("admin/users.html", context)


@router.post("/users/{user_id}/lock")
def lock_user(
    user_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_locked = True
    session.add(user)
    session.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/unlock")
def unlock_user(
    user_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_locked = False
    session.add(user)
    session.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/force-reset")
def force_reset(
    user_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.require_password_reset = True
    user.password_reset_token = token_urlsafe(16)
    session.add(user)
    session.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/scans", response_class=HTMLResponse)
def admin_scans(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    scan_service = ScanService(session)
    scans = scan_service.list_scans()
    queue = session.exec(select(ScanJob).order_by(ScanJob.created_at.desc()).limit(25)).all()
    context = {
        **admin_base_context(request, "scans", session, current_user),
        "scans": scans,
        "queue": queue,
        "queue_snapshot": system.worker_queue_snapshot(session),
    }
    return templates.TemplateResponse("admin/scans.html", context)


@router.get("/system", response_class=HTMLResponse)
def admin_system(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    context = {
        **admin_base_context(request, "system", session, current_user),
        "queue_snapshot": system.worker_queue_snapshot(session),
        "worker_statuses": system.worker_status_list(session),
        "system_health": system.system_health_snapshot(session),
    }
    return templates.TemplateResponse("admin/system.html", context)


@router.get("/logs", response_class=HTMLResponse)
def admin_logs(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    logs = session.exec(select(PlatformLog).order_by(PlatformLog.created_at.desc()).limit(100)).all()
    context = {**admin_base_context(request, "logs", session, current_user), "logs": logs}
    return templates.TemplateResponse("admin/logs.html", context)


@router.get("/flags", response_class=HTMLResponse)
def admin_flags(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> HTMLResponse:
    feature_flags = flags.list_feature_flags(session)
    context = {**admin_base_context(request, "flags", session, current_user), "flags": feature_flags}
    return templates.TemplateResponse("admin/feature_flags.html", context)


@router.post("/flags")
def create_feature_flag(
    key: str = Form(...),
    description: str = Form(""),
    enabled: bool = Form(False),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    flags.create_flag(session, key=key, description=description, enabled=enabled)
    return RedirectResponse(url="/admin/flags", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/flags/{flag_id}/toggle")
def toggle_feature_flag(
    flag_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_super_admin),
) -> RedirectResponse:
    flags.toggle_flag(session, flag_id)
    return RedirectResponse(url="/admin/flags", status_code=status.HTTP_303_SEE_OTHER)
