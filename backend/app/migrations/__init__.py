from __future__ import annotations

from typing import Iterable, Protocol

from sqlalchemy.engine import Engine


class Migration(Protocol):
    def apply(self, engine: Engine) -> None:
        ...


def run_migrations(engine: Engine) -> None:
    """Execute lightweight SQL migrations during startup."""

    from . import super_admin_flag

    migrations: Iterable[Migration] = (super_admin_flag,)  # type: ignore[assignment]
    for migration in migrations:
        try:
            migration.apply(engine)
        except Exception:
            # Migrations are best-effort for dev/test sqlite databases. Failures
            # should not prevent the API from starting, but we log them for
            # troubleshooting via a print so test output shows the failure.
            print(f"[migrations] failed to apply {migration.__name__}")  # pragma: no cover
