from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable

from sqlmodel import Session, select

try:  # dual import roots for tests vs runtime
    from app.models import RuleGroup, ScanJob, Schedule  # type: ignore
    from app.security.audit import log_action  # type: ignore
    from app.security.config import security_settings  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.models import RuleGroup, ScanJob, Schedule  # type: ignore
    from backend.app.security.audit import log_action  # type: ignore
    from backend.app.security.config import security_settings  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ScheduleManager:
    def __init__(self, session_factory: Callable[[], Session], poll_interval_seconds: int = 60):
        self.session_factory = session_factory
        self.poll_interval_seconds = poll_interval_seconds
        self._stopping = False

    async def start(self) -> None:
        logger.info("Starting CompliancePulse scheduler loop")
        while not self._stopping:
            await self._run_once()
            await asyncio.sleep(self.poll_interval_seconds)

    async def _run_once(self) -> None:
        now = datetime.utcnow()
        session = self.session_factory()
        try:
            schedules = session.exec(select(Schedule).where(Schedule.enabled == True)).all()  # noqa: E712
            for schedule in schedules:
                next_run = schedule.next_run or now
                if next_run <= now:
                    self._enqueue_job(session, schedule)
        finally:
            session.close()

    def _enqueue_job(self, session: Session, schedule: Schedule) -> None:
        group = session.get(RuleGroup, schedule.group_id)
        if not group:
            return
        if not self._group_has_capacity(session, group.id):
            logger.debug("Skipping enqueue for group %s due to pending jobs", group.id)
            return
        job = ScanJob(
            group_id=group.id,
            schedule_id=schedule.id,
            hostname=group.default_hostname,
            triggered_by=f"schedule:{schedule.id}",
            organization_id=schedule.organization_id,
        )
        session.add(job)
        schedule.next_run = datetime.utcnow() + timedelta(minutes=max(schedule.interval_minutes or 60, 5))
        schedule.updated_at = datetime.utcnow()
        session.add(schedule)
        try:
            session.commit()
            logger.info("Queued scan job %s for group %s", job.id, group.name)
            log_action(
                action_type="SCAN_SANDBOX_EVENT",
                resource_type="RULE_GROUP",
                resource_id=group.id,
                request=None,
                user=None,
                org=None,
                metadata={"job_id": job.id, "trigger": "scheduler"},
            )
        except Exception:
            session.rollback()
            logger.exception("Failed to enqueue scan job for schedule %s", schedule.id)

    async def stop(self) -> None:
        self._stopping = True

    def _group_has_capacity(self, session: Session, group_id: int) -> bool:
        pending_jobs = session.exec(
            select(ScanJob).where(
                ScanJob.group_id == group_id,
                ScanJob.status.in_(["pending", "running"]),
            )
        ).all()
        return len(pending_jobs) < security_settings.max_concurrent_jobs_per_org
