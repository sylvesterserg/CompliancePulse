from __future__ import annotations

import os
from typing import List

from pydantic import BaseModel, Field, validator


class SecuritySettings(BaseModel):
    """Security-centric configuration flags loaded from environment variables."""

    session_secret_key: str = Field(..., description="Signing key for session + CSRF tokens")
    stripe_webhook_secret: str | None = Field(default=None)
    api_key_hash_salt: str = Field(..., description="Salt for API key hashing")
    rate_limit_backend: str = Field(default=os.getenv("RATE_LIMIT_BACKEND", "memory"))
    log_level: str = Field(default=os.getenv("SECURITY_LOG_LEVEL", "INFO"))
    audit_log_retention_days: int = Field(default=int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "180")))
    security_test_mode: bool = Field(default=os.getenv("SECURITY_TEST_MODE", "0") == "1")
    allowed_commands: List[str] = Field(default_factory=list)
    max_scan_runtime_per_job: int = Field(default=int(os.getenv("MAX_SCAN_RUNTIME_PER_JOB", "900")))
    max_concurrent_jobs_per_org: int = Field(default=int(os.getenv("MAX_CONCURRENT_JOBS_PER_ORG", "3")))
    api_key_rate_limit: int = Field(default=int(os.getenv("API_KEY_RATE_LIMIT", "1000")))
    api_key_rate_window_seconds: int = Field(default=int(os.getenv("API_KEY_RATE_WINDOW_SECONDS", "3600")))

    @validator("allowed_commands", pre=True, always=True)
    def _parse_allowed_commands(cls, value: object) -> List[str]:
        if isinstance(value, list):
            return value
        env_value = os.getenv("ALLOWED_COMMANDS")
        if env_value:
            commands = [item.strip() for item in env_value.split(",") if item.strip()]
        else:
            commands = [
                "cat",
                "grep",
                "rpm",
                "dpkg",
                "stat",
                "systemctl",
                "test",
            ]
        return commands


def _derive_required_secret(name: str, default: str | None = None) -> str:
    env_value = os.getenv(name)
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if env_value:
        return env_value
    if environment in {"development", "test", "testing"} and default:
        return default
    raise RuntimeError(f"Missing required security environment variable: {name}")


security_settings = SecuritySettings(
    session_secret_key=_derive_required_secret("SESSION_SECRET_KEY", "dev-session-key"),
    api_key_hash_salt=_derive_required_secret("API_KEY_HASH_SALT", "dev-api-salt"),
    stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
)

__all__ = ["security_settings", "SecuritySettings"]
