from __future__ import annotations

from functools import lru_cache

from .utils import SessionStore


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    from ..config import settings

    return SessionStore(
        secret=settings.session_secret,
        default_ttl=settings.session_max_age,
        backend=settings.session_backend,
        redis_url=settings.redis_url,
    )


__all__ = ["get_session_store", "SessionStore"]
