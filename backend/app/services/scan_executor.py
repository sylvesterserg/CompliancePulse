from __future__ import annotations

"""
Adapter for the engine ScanExecutor exposed under app.services.

This ensures imports like `from app.services.scan_executor import ScanExecutor`
resolve, while providing a minimal `execute(job)` API used by some tests.
"""

from typing import Any, Dict

from sqlmodel import Session

# Delegate to the full-featured engine implementation.
from backend.engine.scan_executor import (
    ScanExecutor as _EngineScanExecutor,
    ScanExecutionResult,
)  # type: ignore
try:
    from app.models import ScanResult, ScanJob  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.models import ScanResult, ScanJob  # type: ignore


class ScanExecutor(_EngineScanExecutor):
    """Service-layer ScanExecutor shim.

    - Accepts a Session (via super().__init__).
    - Exposes `execute(job)` in addition to the engine's methods to
      maintain compatibility with older tests/usages.
    """

    def __init__(self, session: Session, organization_id: int, **kwargs: Any) -> None:  # noqa: D401
        super().__init__(session=session, organization_id=organization_id, **kwargs)

    # Minimal compatibility method expected by some tests/consumers.
    def execute(self, job: ScanJob) -> Dict[str, Any]:
        """Execute a ScanJob and return a compact payload.

        Returns a dict shaped like:
            {"id": result.id, "results": result.result}

        For compatibility, "results" is populated with the primary result's
        stdout (if present); if no results are produced, values are None.
        """

        # Prefer the engine's job executor when available.
        exec_result: ScanExecutionResult = self.execute_job(job)
        primary: ScanResult | None = exec_result.results[0] if exec_result.results else None
        return {
            "id": primary.id if primary else None,
            # "result.result" isn't a concrete field on ScanResult; map to stdout for brevity.
            "results": primary.stdout if primary else None,
        }
