import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if BACKEND.as_posix() not in sys.path:
    sys.path.insert(0, BACKEND.as_posix())

from app.models import Organization, RuleGroup, Schedule  # type: ignore  # noqa: E402
from engine.scheduler import ScheduleManager  # type: ignore  # noqa: E402


@pytest.mark.worker
def test_scheduler_enqueues_job(db_engine):
    def sf() -> Session:
        return Session(db_engine)

    # Create minimal org, group, and schedule
    with Session(db_engine) as s:
        org = s.exec(select(Organization)).first()
        if not org:
            org = Organization(name="Sched Org", slug="sched")
            s.add(org)
            s.commit()
            s.refresh(org)
        group = s.exec(select(RuleGroup).where(RuleGroup.organization_id == org.id)).first()
        if not group:
            group = RuleGroup(
                organization_id=org.id,
                name="Sched Group",
                benchmark_id="rocky_l1_foundation",
            )
            s.add(group)
            s.commit()
            s.refresh(group)
        sched = s.exec(select(Schedule).where(Schedule.group_id == group.id)).first()
        if not sched:
            sched = Schedule(
                organization_id=org.id,
                name="Immediate",
                group_id=group.id,
                frequency="custom",
                interval_minutes=5,
                enabled=True,
                next_run=datetime.utcnow() - timedelta(minutes=1),
            )
            s.add(sched)
            s.commit()

    manager = ScheduleManager(session_factory=sf, poll_interval_seconds=0)
    # Run one iteration synchronously
    import asyncio

    asyncio.run(manager._run_once())  # type: ignore[attr-defined]

    with Session(db_engine) as s:
        from app.models import ScanJob  # type: ignore

        jobs = s.exec(select(ScanJob)).all()
        assert jobs, "Expected at least one job enqueued by scheduler"
