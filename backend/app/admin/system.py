from __future__ import annotations

import json
from typing import Dict, List

from sqlmodel import Session, func, select

from ..models import PlatformLog, Scan, ScanJob, Schedule, WorkerStatus


def worker_queue_snapshot(session: Session) -> Dict[str, int]:
    pending = session.exec(select(func.count(ScanJob.id)).where(ScanJob.status == "pending")).one()
    running = session.exec(select(func.count(ScanJob.id)).where(ScanJob.status == "running")).one()
    completed = session.exec(select(func.count(ScanJob.id)).where(ScanJob.status == "completed")).one()
    return {"pending": pending, "running": running, "completed": completed}


def worker_status_list(session: Session) -> List[Dict]:
    statuses = session.exec(select(WorkerStatus).order_by(WorkerStatus.worker_type)).all()
    return [
        {
            "id": status.id,
            "worker_type": status.worker_type,
            "status": status.status,
            "queue_depth": status.queue_depth,
            "last_heartbeat": status.last_heartbeat,
            "details": json.loads(status.details_json or "{}"),
            "updated_at": status.updated_at,
        }
        for status in statuses
    ]


def system_health_snapshot(session: Session) -> Dict:
    next_schedule = (
        session.exec(
            select(Schedule)
            .where(Schedule.enabled == True)  # noqa: E712
            .order_by(Schedule.next_run)
        )
        .first()
    )
    recent_logs = session.exec(select(PlatformLog).order_by(PlatformLog.created_at.desc()).limit(10)).all()
    logs = [
        {
            "source": log.source,
            "level": log.level,
            "message": log.message,
            "created_at": log.created_at,
        }
        for log in recent_logs
    ]
    active_scans = session.exec(
        select(Scan)
        .where(~Scan.status.in_(["completed", "passed"]))
        .order_by(Scan.started_at.desc())
        .limit(10)
    ).all()
    scans = [
        {
            "id": scan.id,
            "hostname": scan.hostname,
            "status": scan.status,
            "started_at": scan.started_at,
            "organization_id": scan.organization_id,
            "benchmark_id": scan.benchmark_id,
        }
        for scan in active_scans
    ]
    return {
        "next_schedule": next_schedule.next_run if next_schedule else None,
        "logs": logs,
        "active_scans": scans,
    }
