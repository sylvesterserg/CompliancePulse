from __future__ import annotations

import json
from typing import Dict, List

from sqlmodel import Session, func, select

from ..models import (
    Organization,
    OrganizationMembership,
    PlatformLog,
    Rule,
    Scan,
    ScanJob,
    Schedule,
    User,
)


def dashboard_metrics(session: Session) -> dict:
    totals = {
        "organizations": session.exec(select(func.count(Organization.id))).one(),
        "users": session.exec(select(func.count(User.id))).one(),
        "rules": session.exec(select(func.count(Rule.id))).one(),
        "active_scans": session.exec(select(func.count(Scan.id))).one(),
        "schedules": session.exec(select(func.count(Schedule.id))).one(),
    }

    plan_breakdown = (
        session.exec(
            select(Organization.plan_tier, func.count(Organization.id)).group_by(Organization.plan_tier)
        ).all()
    )
    plan_totals = {plan: count for plan, count in plan_breakdown}

    recent_logs = session.exec(select(PlatformLog).order_by(PlatformLog.created_at.desc()).limit(5)).all()
    logs = [
        {
            "id": log.id,
            "message": log.message,
            "source": log.source,
            "level": log.level,
            "created_at": log.created_at,
            "details": json.loads(log.details_json or "{}"),
        }
        for log in recent_logs
    ]

    return {"totals": totals, "plan_breakdown": plan_totals, "recent_logs": logs}


def list_organizations(session: Session) -> List[Dict]:
    organizations = session.exec(select(Organization).order_by(Organization.created_at.desc())).all()
    data: List[Dict] = []
    for org in organizations:
        member_count = session.exec(
            select(func.count(OrganizationMembership.id)).where(OrganizationMembership.organization_id == org.id)
        ).one()
        active_scans = session.exec(
            select(func.count(Scan.id)).where(Scan.organization_id == org.id)
        ).one()
        pending_jobs = session.exec(
            select(func.count(ScanJob.id)).where(
                (ScanJob.organization_id == org.id) & (ScanJob.status == "pending")
            )
        ).one()
        upcoming_schedule = (
            session.exec(
                select(Schedule)
                .where((Schedule.organization_id == org.id) & (Schedule.enabled == True))  # noqa: E712
                .order_by(Schedule.next_run)
            )
            .first()
        )
        data.append(
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "plan_tier": org.plan_tier,
                "seat_limit": org.seat_limit,
                "subscription_status": org.subscription_status,
                "subscription_renews_at": org.subscription_renews_at,
                "stripe_customer_id": org.stripe_customer_id,
                "stripe_subscription_id": org.stripe_subscription_id,
                "is_active": org.is_active,
                "suspended_at": org.suspended_at,
                "member_count": member_count,
                "active_scans": active_scans,
                "pending_jobs": pending_jobs,
                "next_schedule": upcoming_schedule.next_run if upcoming_schedule else None,
                "created_at": org.created_at,
                "updated_at": org.updated_at,
            }
        )
    return data


def list_users(session: Session) -> List[Dict]:
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    data: List[Dict] = []
    for user in users:
        memberships = session.exec(
            select(OrganizationMembership, Organization)
            .join(Organization, OrganizationMembership.organization_id == Organization.id)
            .where(OrganizationMembership.user_id == user.id)
        ).all()
        organizations = [
            {
                "id": org.id,
                "name": org.name,
                "role": membership.role,
                "plan_tier": org.plan_tier,
            }
            for membership, org in memberships
        ]
        data.append(
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_locked": user.is_locked,
                "super_admin": user.super_admin,
                "require_password_reset": user.require_password_reset,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
                "organizations": organizations,
                "password_reset_token": user.password_reset_token,
            }
        )
    return data
