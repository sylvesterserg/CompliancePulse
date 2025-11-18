from __future__ import annotations

import threading
import time
from typing import Dict, Tuple

from fastapi import HTTPException, Request, status

from .config import security_settings


class MemoryRateLimitStore:
    def __init__(self) -> None:
        self._hits: Dict[str, Tuple[float, int]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            window_start, count = self._hits.get(key, (now, 0))
            if now - window_start >= window_seconds:
                window_start = now
                count = 0
            count += 1
            self._hits[key] = (window_start, count)
            if count > limit:
                retry_after = int(window_seconds - (now - window_start))
                return False, max(retry_after, 1)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_rate_limit_store = MemoryRateLimitStore()


def _get_store() -> MemoryRateLimitStore:
    return _rate_limit_store


def rate_limit(name: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        identifier = request.headers.get("x-forwarded-for")
        if not identifier and request.client:
            identifier = request.client.host
        identifier = identifier or "anonymous"
        key = f"{name}:{identifier}"
        allowed, retry_after = _get_store().hit(key, limit, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


def enforce_api_key_limit(api_key_prefix: str) -> None:
    allowed, retry_after = _get_store().hit(
        key=f"api-key:{api_key_prefix}",
        limit=security_settings.api_key_rate_limit,
        window_seconds=security_settings.api_key_rate_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="API key rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def reset_rate_limits() -> None:
    _get_store().reset()
