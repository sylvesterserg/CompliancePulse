"""Lightweight package init for app.

Avoid importing FastAPI application at import time to prevent side effects
in environments (like tests) that only need configs/models.
"""

__all__ = []
