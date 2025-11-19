from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel
try:
    from .version import APP_VERSION as _DEFAULT_VERSION
except Exception:  # pragma: no cover
    _DEFAULT_VERSION = "1.0.0-alpha"


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "compliancepulse.db"


class Settings(BaseModel):
    """Runtime configuration for the CompliancePulse API."""

    app_name: str = "CompliancePulse API"
    version: str = _DEFAULT_VERSION
    environment: str = "development"
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    benchmark_dir: Path = BACKEND_ROOT / "benchmarks"
    allow_origins: list[str] = ["*"]
    shell_timeout: int = 15
    data_dir: Path = BACKEND_ROOT / "data"
    logs_dir: Path = BACKEND_ROOT / "logs"
    artifacts_dir: Path = BACKEND_ROOT / "artifacts"
    frontend_dir: Path = PROJECT_ROOT / "frontend"
    frontend_template_dir: Path = PROJECT_ROOT / "frontend" / "templates"
    frontend_static_dir: Path = PROJECT_ROOT / "frontend" / "static"
    session_cookie_name: str = "cp_session"
    session_secret: str = "change-me-session-secret"
    session_max_age: int = 60 * 60 * 24 * 7
    session_backend: str = "memory"
    redis_url: str | None = None
    cookie_secure: bool = False
    csrf_header_name: str = "X-CSRF-Token"

    @classmethod
    def load(cls) -> "Settings":
        import os

        values: dict[str, object] = {}
        db_url = os.getenv("DB_URL")
        app_version = os.getenv("APP_VERSION")
        benchmark_dir = os.getenv("BENCHMARK_DIR")
        timeout = os.getenv("SHELL_TIMEOUT")
        environment = os.getenv("ENVIRONMENT")
        if environment:
            values["environment"] = environment
        if db_url:
            values["database_url"] = db_url
        if benchmark_dir:
            values["benchmark_dir"] = Path(benchmark_dir)
        if timeout:
            values["shell_timeout"] = int(timeout)
        data_dir = os.getenv("DATA_DIR")
        logs_dir = os.getenv("LOGS_DIR")
        artifacts_dir = os.getenv("ARTIFACTS_DIR")
        if data_dir:
            values["data_dir"] = Path(data_dir)
        if logs_dir:
            values["logs_dir"] = Path(logs_dir)
        if artifacts_dir:
            values["artifacts_dir"] = Path(artifacts_dir)
        frontend_templates = os.getenv("FRONTEND_TEMPLATES")
        frontend_static = os.getenv("FRONTEND_STATIC")
        if frontend_templates:
            values["frontend_template_dir"] = Path(frontend_templates)
        if frontend_static:
            values["frontend_static_dir"] = Path(frontend_static)
        # Support both SESSION_SECRET and SESSION_SECRET_KEY (used by security settings)
        session_secret = os.getenv("SESSION_SECRET") or os.getenv("SESSION_SECRET_KEY")
        if session_secret:
            values["session_secret"] = session_secret
        cookie_name = os.getenv("SESSION_COOKIE_NAME")
        if cookie_name:
            values["session_cookie_name"] = cookie_name
        session_max_age = os.getenv("SESSION_MAX_AGE")
        if session_max_age:
            values["session_max_age"] = int(session_max_age)
        session_backend = os.getenv("SESSION_BACKEND")
        if session_backend:
            values["session_backend"] = session_backend
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            values["redis_url"] = redis_url
        cookie_secure = os.getenv("SESSION_SECURE_COOKIE")
        if cookie_secure:
            values["cookie_secure"] = cookie_secure.lower() in {"1", "true", "yes"}
        csrf_header = os.getenv("CSRF_HEADER_NAME")
        if csrf_header:
            values["csrf_header_name"] = csrf_header
        # Optional CORS origins configuration
        allowed_origins = os.getenv("ALLOWED_ORIGINS")
        if allowed_origins:
            values["allow_origins"] = [x.strip() for x in allowed_origins.split(",") if x.strip()]
        if app_version:
            values["version"] = app_version
        return cls(**values)


settings = Settings.load()
