from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Session, func, select

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from backend.app.billing.utils import get_billing_state, plan_allows_feature
from backend.app.database import engine
from backend.app.models import Scan, ScanJob, Schedule
from .engine.scan_executor import ScanExecutor

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


def _automation_allowed(session: Session) -> tuple[bool, bool]:
    organization = get_billing_state(session)
    if not organization:
        return True, True
    allow_ai = plan_allows_feature(organization, "ai_summaries")
    if not organization.is_subscription_active():
        logger.warning("Subscription inactive - scheduler paused")
        return False, allow_ai
    if not plan_allows_feature(organization, "schedules"):
        logger.warning("Current plan does not allow automated schedules")
        return False, allow_ai
    if organization.current_plan == "free" and not organization.is_trial_active():
        window_start = datetime.utcnow() - timedelta(hours=1)
        scan_count = session.exec(select(func.count(Scan.id)).where(Scan.started_at >= window_start)).one()
        if scan_count >= 3:
            logger.info("Free plan rate limit hit (%s scans/hr)", scan_count)
            return False, allow_ai
    return True, allow_ai


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
        allowed, allow_ai = _automation_allowed(session)
        if not allowed:
            job.status = "paused"
            job.error = "Subscription inactive or plan limit"
            session.add(job)
            session.commit()
            return True
        executor = ScanExecutor(session)
        try:
            result = executor.execute_job(job, allow_ai_summary=allow_ai)
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
