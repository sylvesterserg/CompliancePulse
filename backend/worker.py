from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime

from sqlmodel import Session, select

from app.database import engine
from app.models import ScanJob, Schedule
from app.security.audit import log_action
from app.security.config import security_settings
from engine.scan_executor import ScanExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] worker: %(message)s")
logger = logging.getLogger("compliancepulse.worker")

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
MAX_RUNTIME_SECONDS = security_settings.max_scan_runtime_per_job
MAX_CONCURRENT_JOBS = security_settings.max_concurrent_jobs_per_org
FAILURE_COUNTS: dict[int, int] = defaultdict(int)


def _claim_job(session: Session) -> ScanJob | None:
    if not _has_capacity(session):
        logger.debug("Skipping job claim due to concurrency cap")
        return None
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


def _has_capacity(session: Session) -> bool:
    active = session.exec(select(ScanJob).where(ScanJob.status == "running")).all()
    return len(active) < MAX_CONCURRENT_JOBS


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
            FAILURE_COUNTS[job.group_id] += 1
            logger.exception("Job %s failed", job.id)
            log_action(
                action_type="SCAN_SANDBOX_EVENT",
                resource_type="SCAN_JOB",
                resource_id=job.id,
                request=None,
                user=None,
                org=None,
                metadata={"error": str(exc), "group_id": job.group_id},
            )
        job.completed_at = datetime.utcnow()
        session.add(job)
        _mark_schedule_run(session, job.schedule_id, job.completed_at)
        _enforce_runtime(job)
        if FAILURE_COUNTS.get(job.group_id, 0) >= 3:
            logger.warning(
                "Group %s has %s consecutive failures",
                job.group_id,
                FAILURE_COUNTS[job.group_id],
            )
            log_action(
                action_type="SCAN_SANDBOX_EVENT",
                resource_type="RULE_GROUP",
                resource_id=job.group_id,
                request=None,
                user=None,
                org=None,
                metadata={"failure_count": FAILURE_COUNTS[job.group_id]},
            )
        session.commit()
        return True
    finally:
        session.close()


def _enforce_runtime(job: ScanJob) -> None:
    if not job.started_at or not job.completed_at:
        return
    runtime = (job.completed_at - job.started_at).total_seconds()
    if runtime <= MAX_RUNTIME_SECONDS:
        return
    job.status = "failed"
    job.error = f"Runtime exceeded {MAX_RUNTIME_SECONDS}s"
    log_action(
        action_type="SCAN_SANDBOX_EVENT",
        resource_type="SCAN_JOB",
        resource_id=job.id,
        request=None,
        user=None,
        org=None,
        metadata={"runtime": runtime, "max_runtime": MAX_RUNTIME_SECONDS},
    )


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
