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

    @classmethod
    def load(cls) -> "Settings":
        import os

        values: dict[str, object] = {}
        db_url = os.getenv("DB_URL")
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
        return cls(**values)


settings = Settings.load()
