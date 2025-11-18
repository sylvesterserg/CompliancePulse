"""Lightweight package init for security.

Avoid eager imports to prevent circular dependencies during test collection.
Submodules should be imported directly, e.g. `from app.security.config import security_settings`.
"""

__all__: list[str] = []
