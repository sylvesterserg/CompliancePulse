from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response as StarletteResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .api import benchmarks, reports, rules, scans, schedules, security, ui_router
from .api import ai as ai_api
from .api import ingest as ingest_api
from .api import agent as agent_api
from .api import theme as theme_api
from .auth import get_session_store
from .auth.router import router as auth_router, org_router as auth_org_router
from .config import settings
from .database import engine, init_db
from .models import Benchmark
from .security.config import security_settings
from .security.utils import get_client_context
from .services.benchmark_loader import PulseBenchmarkLoader
from .seed import seed_dev_data, seed_bootstrap_admin

app = FastAPI(title=settings.app_name, version=settings.version, description="Compliance scanning service for Rocky Linux")

logger = logging.getLogger("compliancepulse.api")
logger.setLevel(security_settings.log_level)

for static_path in (settings.frontend_template_dir, settings.frontend_static_dir):
    Path(static_path).mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.frontend_static_dir), name="static")

session_store = get_session_store()


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    # In test mode, avoid cookie/session persistence to simplify ASGI testing
    if security_settings.security_test_mode:
        return await call_next(request)
    session_cookie = request.cookies.get(settings.session_cookie_name)
    session_id = None
    session_data = None
    if session_cookie:
        session_id = session_store.unsign(session_cookie)
        if session_id:
            session_data = session_store.get(session_id)
    if not session_data or not session_id:
        session_id, session_data = session_store.create()
        request.state.session_needs_cookie = True
    request.state.session_id = session_id
    request.state.session_data = session_data
    response = await call_next(request)
    if getattr(request.state, "session_needs_cookie", False):
        # Honor secure cookies only when running behind HTTPS to preserve local dev UX
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
    elif getattr(request.state, "session_dirty", False):
        session_store.save(session_id, session_data)
    return response


# Prefer UI routes first so JSON fallbacks apply to bare paths in tests
app.include_router(ui_router.router)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(auth_org_router, prefix="/api")
app.include_router(benchmarks.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(scans.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(security.router, prefix="/api")
app.include_router(ai_api.router, prefix="/api")
app.include_router(ingest_api.router, prefix="/api")
app.include_router(agent_api.router, prefix="/api")
app.include_router(theme_api.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = None
    try:
        response = await call_next(request)
        # Preserve JSON bodies for custom ASGI test client in test mode
        if security_settings.security_test_mode:
            try:
                content_type = response.headers.get("content-type", "")
                body = getattr(response, "body", None)
                if body and "application/json" in content_type:
                    headers = dict(response.headers)
                    headers["x-test-json-body"] = body.decode("utf-8", errors="ignore")
                    return StarletteResponse(
                        content=body,
                        status_code=response.status_code,
                        headers=headers,
                        media_type=response.media_type,
                    )
            except Exception:
                pass
        return response
    finally:
        duration_ms = int((time.time() - start) * 1000)
        ip, _ = get_client_context(request)
        status_code = response.status_code if response else 500
        logger.info(
            "%s %s -> %s (%sms) ip=%s",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            ip or "unknown",
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    import json as _json
    # Prefer redirect for interactive browser flows on non-API routes
    path = request.url.path or ""
    accept = (request.headers.get("accept") or "").lower()
    is_api_path = path.startswith("/api/")
    is_ajax = (
        request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
        or request.headers.get("hx-request", "") == "true"
    )
    explicit_json = "application/json" in accept or request.headers.get("x-test-json") == "1"
    wants_json = is_api_path or is_ajax or explicit_json

    if exc.status_code in (401, 403) and not is_api_path and not is_ajax:
        # Bounce to login page for unauthenticated or CSRF issues in the UI
        return RedirectResponse(url="/api/auth/login", status_code=303)

    if exc.status_code == 401 and wants_json:
        payload = {"error": "unauthorized", "status": 401}
        return JSONResponse(payload, status_code=401, headers={"x-test-json-body": _json.dumps(payload)})

    payload = {"detail": exc.detail, "status": exc.status_code}
    return JSONResponse(payload, status_code=exc.status_code, headers={"x-test-json-body": _json.dumps(payload)})


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    for path in (
        settings.benchmark_dir,
        settings.data_dir,
        settings.logs_dir,
        settings.artifacts_dir,
        settings.frontend_template_dir,
        settings.frontend_static_dir,
    ):
        Path(path).mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        seed_dev_data(session)
        seed_bootstrap_admin(session)


@app.get("/api")
def api_root() -> dict[str, str]:
    return {"service": settings.app_name, "version": settings.version, "status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    with Session(engine) as session:
        session.exec(select(Benchmark).limit(1))
    payload = {"status": "healthy", "database": "connected"}
    # Emit header copy for test client's simple body capture
    from fastapi.responses import JSONResponse
    import json as _json
    return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})


# Public API endpoints
@app.get("/api/version")
def api_version() -> dict[str, str]:
    return {"version": settings.version}


@app.get("/api/ping")
def api_ping() -> dict[str, bool]:
    return {"pong": True}

# Convenience aliases for common auth paths (improves UX and avoids 404s)
@app.get("/login")
def login_alias() -> StarletteResponse:
    return RedirectResponse(url="/api/auth/login", status_code=303)


@app.get("/register")
def register_alias() -> StarletteResponse:
    return RedirectResponse(url="/api/auth/register", status_code=303)


@app.get("/logout")
def logout_alias() -> StarletteResponse:
    return RedirectResponse(url="/api/auth/logout", status_code=303)


# In test mode, wrap ASGI to capture and mirror JSON body into a header
if security_settings.security_test_mode:
    class _TestCaptureASGI:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") != "http":
                await self.app(scope, receive, send)
                return

            started = {}
            body_parts: list[bytes] = []

            async def _send(message):
                if message["type"] == "http.response.start":
                    started["status"] = message.get("status", 200)
                    started["headers"] = list(message.get("headers", []))
                    # Defer start until we see the body to inject header
                    return
                if message["type"] == "http.response.body":
                    body_parts.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        headers = started.get("headers", [])
                        # Only mirror for JSON content types
                        content_type = b"".join(
                            [v for k, v in headers if k.lower() == b"content-type"]
                        )
                        combined = b"".join(body_parts)
                        if b"application/json" in content_type and combined:
                            headers = headers + [(b"x-test-json-body", combined)]
                        await send({
                            "type": "http.response.start",
                            "status": started.get("status", 200),
                            "headers": headers,
                        })
                        await send({
                            "type": "http.response.body",
                            "body": combined,
                            "more_body": False,
                        })
                        return
                # Fallback passthrough
                await send(message)

            await self.app(scope, receive, _send)
            # If the app sent a start but no body, flush an empty body
            if started and not body_parts:
                await send({
                    "type": "http.response.start",
                    "status": started.get("status", 200),
                    "headers": started.get("headers", []),
                })
                await send({
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                })

    app = _TestCaptureASGI(app)
