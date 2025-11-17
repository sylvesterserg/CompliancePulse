from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "compliancepulse.db"


class Settings(BaseModel):
    """Runtime configuration for the CompliancePulse API."""

    app_name: str = "CompliancePulse API"
    version: str = "0.4.0"
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
    app_base_url: str = "http://localhost:8000"
    stripe_public_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_free: str = "price_free"
    stripe_price_pro: str = "price_pro"
    stripe_price_enterprise: str = "price_enterprise"
    billing_owner_token: str | None = None
    trial_days: int = 14

    @classmethod
    def load(cls) -> "Settings":
        import os

        values: dict[str, object] = {}
        db_url = os.getenv("DB_URL")
        benchmark_dir = os.getenv("BENCHMARK_DIR")
        timeout = os.getenv("SHELL_TIMEOUT")
        environment = os.getenv("ENVIRONMENT")
        app_base_url = os.getenv("APP_BASE_URL")
        if app_base_url:
            values["app_base_url"] = app_base_url.rstrip("/")
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
        stripe_public_key = os.getenv("STRIPE_PUBLIC_KEY")
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        stripe_price_free = os.getenv("STRIPE_PRICE_FREE")
        stripe_price_pro = os.getenv("STRIPE_PRICE_PRO")
        stripe_price_enterprise = os.getenv("STRIPE_PRICE_ENTERPRISE")
        billing_owner_token = os.getenv("BILLING_OWNER_TOKEN")
        trial_days = os.getenv("TRIAL_DAYS")
        if stripe_public_key:
            values["stripe_public_key"] = stripe_public_key
        if stripe_secret_key:
            values["stripe_secret_key"] = stripe_secret_key
        if stripe_webhook_secret:
            values["stripe_webhook_secret"] = stripe_webhook_secret
        if stripe_price_free:
            values["stripe_price_free"] = stripe_price_free
        if stripe_price_pro:
            values["stripe_price_pro"] = stripe_price_pro
        if stripe_price_enterprise:
            values["stripe_price_enterprise"] = stripe_price_enterprise
        if billing_owner_token:
            values["billing_owner_token"] = billing_owner_token
        if trial_days:
            values["trial_days"] = int(trial_days)
        return cls(**values)


settings = Settings.load()
