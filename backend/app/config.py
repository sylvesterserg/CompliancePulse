from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "compliancepulse.db"


class Settings(BaseModel):
    """Runtime configuration for the CompliancePulse API."""

    app_name: str = "CompliancePulse API"
    version: str = "0.3.0"
    environment: str = "development"
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    benchmark_dir: Path = Path(__file__).resolve().parents[1] / "benchmarks"
    allow_origins: list[str] = ["*"]
    shell_timeout: int = 15

    @classmethod
    def load(cls) -> "Settings":
        import os

        values: dict[str, object] = {}
        db_url = os.getenv("DB_URL")
        benchmark_dir = os.getenv("BENCHMARK_DIR")
        timeout = os.getenv("SHELL_TIMEOUT")
        if db_url:
            values["database_url"] = db_url
        if benchmark_dir:
            values["benchmark_dir"] = Path(benchmark_dir)
        if timeout:
            values["shell_timeout"] = int(timeout)
        return cls(**values)


settings = Settings.load()
