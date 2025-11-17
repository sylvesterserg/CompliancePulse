from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from sqlmodel import Session, select

from app.database import engine
from app.models import ScanJob, Schedule
from engine.scan_executor import ScanExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] worker: %(message)s")
logger = logging.getLogger("compliancepulse.worker")

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))


def _claim_job(session: Session) -> ScanJob | None:
    job = session.exec(
        select(ScanJob).where(ScanJob.status == "pending").order_by(ScanJob.created_at)
    ).first()
    if not job:
        return None
    job.status = "running"
    job.started_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _mark_schedule_run(session: Session, schedule_id: int | None, completed_at: datetime) -> None:
    if not schedule_id:
        return
    schedule = session.get(Schedule, schedule_id)
    if schedule:
        schedule.last_run = completed_at
        session.add(schedule)


def _process_job() -> bool:
    session = Session(engine)
    try:
        job = _claim_job(session)
        if not job:
            return False
        session.info["organization_id"] = job.organization_id
        executor = ScanExecutor(session, organization_id=job.organization_id)
        try:
            result = executor.execute_job(job)
            job.status = "completed"
            job.scan_id = result.scan.id
            job.error = None
        except Exception as exc:  # pragma: no cover - defensive
            job.status = "failed"
            job.error = str(exc)
            logger.exception("Job %s failed", job.id)
        job.completed_at = datetime.utcnow()
        session.add(job)
        _mark_schedule_run(session, job.schedule_id, job.completed_at)
        session.commit()
        return True
    finally:
        session.close()


async def main() -> None:
    logger.info("Worker started with poll interval %ss", POLL_INTERVAL)
    while True:
        processed = _process_job()
        if not processed:
            await asyncio.sleep(POLL_INTERVAL)
        else:
            await asyncio.sleep(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # pragma: no cover - graceful shutdown
        logger.info("Worker stopped")
