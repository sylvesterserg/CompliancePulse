"""Latency benchmark comparing legacy and current API configurations."""
from __future__ import annotations

import asyncio
import os
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Ensure the repository root is importable for local modules (e.g., custom httpx stub).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from sqlmodel import SQLModel, Session, create_engine, select

from httpx import AsyncClient

# Prepare isolated database locations before importing the application engine.
_TEMP_DIR = tempfile.TemporaryDirectory()
_TEMP_PATH = Path(_TEMP_DIR.name)
NEW_DB_PATH = _TEMP_PATH / "new_app.db"
LEGACY_DB_PATH = _TEMP_PATH / "legacy_app.db"

os.environ.setdefault("DB_URL", f"sqlite:///{NEW_DB_PATH}")

from backend.api.models import Report, System  # noqa: E402
from backend.api.routes.scan import ScanRequest, ScanResponse  # noqa: E402
from backend.main import app as current_app  # noqa: E402


def create_legacy_app(database_url: str) -> FastAPI:
    """Create an app that mirrors the previous inline router configuration."""
    legacy_app = FastAPI(title="CompliancePulse API (legacy)")
    engine = create_engine(database_url, echo=True)

    @legacy_app.on_event("startup")
    def startup() -> None:  # pragma: no cover - exercised via benchmark
        SQLModel.metadata.create_all(engine)

    @legacy_app.get("/")
    def root() -> dict[str, str]:
        return {"service": "CompliancePulse API", "version": "0.1.0", "status": "running"}

    @legacy_app.post("/scan", response_model=ScanResponse)
    def scan_system(request: ScanRequest) -> ScanResponse:
        scan_time = datetime.now().isoformat()
        scan_result = ScanResponse(
            hostname=request.hostname,
            score=87,
            issues=[
                "Password policy does not meet CIS standards",
                "Firewall not configured properly",
                "SSH root login enabled",
                "No automatic security updates configured",
            ],
            scan_time=scan_time,
        )

        with Session(engine) as session:
            existing = session.exec(select(System).where(System.hostname == request.hostname)).first()
            if existing:
                system = existing
                system.last_scan = scan_time
            else:
                system = System(hostname=request.hostname, ip=request.ip, last_scan=scan_time)
                session.add(system)

            session.commit()
            session.refresh(system)

            import json  # Local import emulates original implementation cost.

            report = Report(
                system_id=system.id,
                score=scan_result.score,
                issues_json=json.dumps(scan_result.issues),
                created_at=scan_time,
            )
            session.add(report)
            session.commit()

        return scan_result

    return legacy_app


LEGACY_APP = create_legacy_app(f"sqlite:///{LEGACY_DB_PATH}")


@dataclass
class BenchmarkResult:
    label: str
    samples: list[float]

    @property
    def average(self) -> float:
        return statistics.mean(self.samples)


async def measure_latency(app: FastAPI, *, payload: dict[str, object], iterations: int = 10) -> list[float]:
    durations: list[float] = []
    async with AsyncClient(app=app, base_url="http://test") as client:
        for _ in range(iterations):
            start = time.perf_counter()
            response = await client.post("/scan", json=payload)
            response.raise_for_status()
            durations.append((time.perf_counter() - start) * 1000)
    return durations


async def run_benchmark() -> None:
    payload = {"hostname": "benchmark-host", "ip": "10.0.0.99"}

    legacy_samples = await measure_latency(LEGACY_APP, payload=payload)
    current_samples = await measure_latency(current_app, payload=payload)

    legacy_result = BenchmarkResult("legacy", legacy_samples)
    current_result = BenchmarkResult("current", current_samples)

    improvement = ((legacy_result.average - current_result.average) / legacy_result.average) * 100

    print("Legacy average latency: {:.2f} ms".format(legacy_result.average))
    print("Current average latency: {:.2f} ms".format(current_result.average))
    print("Improvement: {:.1f}%".format(improvement))

    assert current_result.average < 200, "Average latency must be under 200 ms"
    assert improvement >= 20, "Latency improvement must be at least 20%"


if __name__ == "__main__":
    asyncio.run(run_benchmark())
