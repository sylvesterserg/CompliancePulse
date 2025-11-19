from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import Response as StarletteResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import MembershipRole, Organization, User, UserOrganization
from ..auth import get_session_store
from ..services.benchmark_loader import PulseBenchmarkLoader
from .dependencies import (
    get_optional_user,
    require_authenticated_user,
    require_role,
    verify_csrf_token,
)
from .forms import LoginForm, OrganizationForm, RegisterForm, ValidationError
from .utils import hash_password, slugify, verify_password

# Expose paths via include_router prefixes in main (e.g., /api/auth, /api)
router = APIRouter(tags=["auth"])
org_router = APIRouter(tags=["organizations"])

_templates = Jinja2Templates(directory=str(settings.frontend_template_dir))
_templates.env.globals.update({"app_name": settings.app_name})


async def _form_data(request: Request) -> Any:
    if hasattr(request.state, "cached_form"):
        return request.state.cached_form
    form = await request.form()
    request.state.cached_form = form
    return form


def _base_context(request: Request, title: str, **extra: Any) -> dict[str, Any]:
    session_data = getattr(request.state, "session_data", None)
    return {
        "request": request,
        "page_title": title,
        "csrf_token": session_data.csrf_token if session_data else "",
        **extra,
    }


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> StarletteResponse:
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    context = _base_context(request, "Sign In")
    return _templates.TemplateResponse("auth/login.html", context)


@router.post("/login", response_class=HTMLResponse, dependencies=[Depends(verify_csrf_token)])
async def login(
    request: Request,
    db: Session = Depends(get_session),
) -> StarletteResponse:
    form_payload = await _form_data(request)
    try:
        form = LoginForm.from_form(form_payload)
    except ValidationError as exc:
        context = _base_context(request, "Sign In", error=exc.errors())
        return _templates.TemplateResponse("auth/login.html", context, status_code=400)
    normalized_email = form.email.lower()
    user = db.exec(select(User).where(User.email == normalized_email)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        context = _base_context(request, "Sign In", error="Invalid email or password")
        return _templates.TemplateResponse("auth/login.html", context, status_code=400)
    membership = db.exec(select(UserOrganization).where(UserOrganization.user_id == user.id)).first()
    if not membership:
        raise HTTPException(status_code=400, detail="User has no organizations configured")
    session_store = get_session_store()
    session_id = getattr(request.state, "session_id", None)
    session_data = getattr(request.state, "session_data", None)
    if not session_id or not session_data:
        session_id, session_data = session_store.create()
        request.state.session_id = session_id
    session_data.user_id = user.id
    session_data.organization_id = membership.organization_id
    session_store.rotate_csrf(session_id, session_data)
    session_store.save(session_id, session_data)
    request.state.session_data = session_data
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    secure_cookie = settings.cookie_secure and forwarded_proto == "https"
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_store.sign(session_id),
        max_age=settings.session_max_age,
        httponly=True,
        secure=secure_cookie,
        samesite="strict",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> StarletteResponse:
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    context = _base_context(request, "Create Account")
    return _templates.TemplateResponse("auth/register.html", context)


def _ensure_unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug = base
    counter = 1
    while db.exec(select(Organization).where(Organization.slug == slug)).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


@router.post("/register", response_class=HTMLResponse, dependencies=[Depends(verify_csrf_token)])
async def register(
    request: Request,
    db: Session = Depends(get_session),
) -> StarletteResponse:
    form_payload = await _form_data(request)
    try:
        form = RegisterForm.from_form(form_payload)
    except ValidationError as exc:
        context = _base_context(request, "Create Account", error=exc.errors())
        return _templates.TemplateResponse("auth/register.html", context, status_code=400)
    normalized_email = form.email.lower()
    existing = db.exec(select(User).where(User.email == normalized_email)).first()
    if existing:
        context = _base_context(request, "Create Account", error="Email already registered")
        return _templates.TemplateResponse("auth/register.html", context, status_code=400)
    slug = _ensure_unique_slug(db, form.organization_name)
    organization = Organization(name=form.organization_name, slug=slug)
    db.add(organization)
    db.flush()
    user = User(email=normalized_email, hashed_password=hash_password(form.password))
    db.add(user)
    db.flush()
    membership = UserOrganization(user_id=user.id, organization_id=organization.id, role=MembershipRole.OWNER)
    db.add(membership)
    db.commit()
    loader = PulseBenchmarkLoader()
    loader.load_all(db, organization.id)
    session_store = get_session_store()
    session_id = getattr(request.state, "session_id", None)
    session_data = getattr(request.state, "session_data", None)
    if not session_id or not session_data:
        session_id, session_data = session_store.create()
        request.state.session_id = session_id
    session_data.user_id = user.id
    session_data.organization_id = organization.id
    session_store.rotate_csrf(session_id, session_data)
    session_store.save(session_id, session_data)
    request.state.session_data = session_data
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    secure_cookie = settings.cookie_secure and forwarded_proto == "https"
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_store.sign(session_id),
        max_age=settings.session_max_age,
        httponly=True,
        secure=secure_cookie,
        samesite="strict",
    )
    return response


@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request) -> HTMLResponse:
    session_store = get_session_store()
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        session_store.destroy(session_id)
        new_id, session_data = session_store.create()
        request.state.session_id = new_id
        request.state.session_data = session_data
        cookie_value = session_store.sign(new_id)
    else:
        cookie_value = None
    context = _base_context(request, "Signed Out")
    response = _templates.TemplateResponse("auth/logout.html", context)
    if cookie_value:
        response.set_cookie(
            key=settings.session_cookie_name,
            value=cookie_value,
            max_age=settings.session_max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
        )
    return response


@org_router.get("/switch/{organization_id}")
async def switch_organization(
    organization_id: int,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_authenticated_user),
) -> RedirectResponse:
    membership = (
        db.exec(
            select(UserOrganization)
            .where(
                (UserOrganization.organization_id == organization_id)
                & (UserOrganization.user_id == user.id)
            )
            .limit(1)
        ).first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="You do not belong to that organization")
    session_store = get_session_store()
    session_id = getattr(request.state, "session_id", None)
    session_data = getattr(request.state, "session_data", None)
    if not session_id or not session_data:
        raise HTTPException(status_code=400, detail="Session missing")
    session_data.organization_id = organization_id
    session_store.rotate_csrf(session_id, session_data)
    session_store.save(session_id, session_data)
    request.state.session_data = session_data
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_store.sign(session_id),
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return response


@org_router.get("/create", response_class=HTMLResponse, dependencies=[Depends(require_role(MembershipRole.ADMIN))])
async def create_org_page(
    request: Request,
    user: User = Depends(require_authenticated_user),
) -> HTMLResponse:
    context = _base_context(request, "Create Organization", current_user=user)
    return _templates.TemplateResponse("auth/org_create.html", context)


@org_router.post(
    "/create",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_token), Depends(require_role(MembershipRole.ADMIN))],
)
async def create_org(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_authenticated_user),
) -> StarletteResponse:
    form_payload = await _form_data(request)
    try:
        form = OrganizationForm.from_form(form_payload)
    except ValidationError as exc:
        context = _base_context(
            request,
            "Create Organization",
            error=exc.errors(),
            current_user=user,
        )
        return _templates.TemplateResponse("auth/org_create.html", context, status_code=400)
    slug = _ensure_unique_slug(db, form.name)
    organization = Organization(name=form.name, slug=slug)
    db.add(organization)
    db.flush()
    membership = UserOrganization(
        user_id=user.id,
        organization_id=organization.id,
        role=MembershipRole.OWNER,
    )
    db.add(membership)
    db.commit()
    loader = PulseBenchmarkLoader()
    loader.load_all(db, organization.id)
    session_store = get_session_store()
    session_id = getattr(request.state, "session_id", None)
    session_data = getattr(request.state, "session_data", None)
    if session_id and session_data:
        session_data.organization_id = organization.id
        session_store.rotate_csrf(session_id, session_data)
        session_store.save(session_id, session_data)
        request.state.session_data = session_data
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        secure_cookie = settings.cookie_secure and forwarded_proto == "https"
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_store.sign(session_id),
            max_age=settings.session_max_age,
            httponly=True,
            secure=secure_cookie,
            samesite="strict",
        )
        return response
    raise HTTPException(status_code=400, detail="Session unavailable")


__all__ = ["router", "org_router"]
