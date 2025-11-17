from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, select

from ..models import RuleGroup, Schedule
from ..schemas import RuleGroupView, ScheduleCreate, ScheduleView


class ScheduleService:
    def __init__(self, session: Session):
        self.session = session

    def list_rule_groups(self) -> List[RuleGroupView]:
        groups = self.session.exec(select(RuleGroup).order_by(RuleGroup.created_at.desc())).all()
        return [self._build_group_view(group) for group in groups]

    def list_schedules(self) -> List[ScheduleView]:
        schedules = self.session.exec(select(Schedule).order_by(Schedule.created_at.desc())).all()
        return [self._build_schedule_view(schedule) for schedule in schedules]

    def get_next_schedule(self) -> Optional[ScheduleView]:
        schedule = (
            self.session.exec(
                select(Schedule)
                .where(Schedule.enabled == True)  # noqa: E712 - SQLAlchemy truthiness
                .order_by(Schedule.next_run)
            )
            .first()
        )
        if not schedule:
            return None
        return self._build_schedule_view(schedule)

    def create_schedule(self, payload: ScheduleCreate) -> ScheduleView:
        group = self.session.get(RuleGroup, payload.group_id)
        if not group:
            raise ValueError("Rule group not found")
        interval = self._resolve_interval(payload)
        schedule = Schedule(
            name=payload.name,
            group_id=group.id,
            organization_id=group.organization_id,
            frequency=payload.frequency,
            interval_minutes=interval,
            enabled=payload.enabled,
            next_run=datetime.utcnow() + timedelta(minutes=interval),
        )
        self.session.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        return self._build_schedule_view(schedule, group)

    def delete_schedule(self, schedule_id: int) -> None:
        schedule = self.session.get(Schedule, schedule_id)
        if not schedule:
            raise ValueError("Schedule not found")
        self.session.delete(schedule)
        self.session.commit()

    def _build_schedule_view(self, schedule: Schedule, group: RuleGroup | None = None) -> ScheduleView:
        group = group or self.session.get(RuleGroup, schedule.group_id)
        group_name = group.name if group else "unknown"
        return ScheduleView(
            id=schedule.id,
            name=schedule.name,
            group_id=schedule.group_id,
            group_name=group_name,
            frequency=schedule.frequency,
            interval_minutes=schedule.interval_minutes,
            enabled=schedule.enabled,
            next_run=schedule.next_run,
            last_run=schedule.last_run,
            timezone=schedule.timezone,
        )

    def _build_group_view(self, group: RuleGroup) -> RuleGroupView:
        return RuleGroupView(
            id=group.id,
            name=group.name,
            benchmark_id=group.benchmark_id,
            description=group.description,
            default_hostname=group.default_hostname,
            default_ip=group.default_ip,
            tags=json.loads(group.tags_json or "[]"),
            rule_count=len(self._group_rule_ids(group)),
            last_run=group.last_run,
        )

    def _group_rule_ids(self, group: RuleGroup) -> List[str]:
        try:
            return json.loads(group.rule_ids_json or "[]")
        except json.JSONDecodeError:
            return []

    def _resolve_interval(self, payload: ScheduleCreate) -> int:
        if payload.frequency == "hourly":
            return 60
        if payload.frequency == "daily":
            return 60 * 24
        if payload.interval_minutes is None:
            raise ValueError("Custom schedules require interval_minutes")
        return max(payload.interval_minutes, 5)
