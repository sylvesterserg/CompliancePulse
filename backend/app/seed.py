from __future__ import annotations

import json
from datetime import datetime, timedelta

from secrets import token_urlsafe

from sqlmodel import Session, select

from .auth.utils import hash_password
from .config import settings
from .models import (
    Benchmark,
    MembershipRole,
    Organization,
    Report,
    Rule,
    RuleGroup,
    Scan,
    Schedule,
    User,
    UserOrganization,
)
from .services.benchmark_loader import PulseBenchmarkLoader


def seed_dev_data(session: Session) -> None:
    """Populate the database with helpful fixtures for local development."""

    if settings.environment.lower() != "development":
        return

    organization = session.exec(select(Organization).where(Organization.slug == "demo-org")).first()
    if not organization:
        organization = Organization(name="Demo Organization", slug="demo-org")
        session.add(organization)
        session.commit()
        session.refresh(organization)

    user = session.exec(select(User).where(User.email == "demo@compliancepulse.io")).first()
    if not user:
        user = User(
            email="demo@compliancepulse.io",
            hashed_password=hash_password("ChangeMe123!"),
            is_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        membership = UserOrganization(
            user_id=user.id,
            organization_id=organization.id,
            role=MembershipRole.OWNER,
        )
        session.add(membership)
        session.commit()

    if not session.exec(select(Rule).where(Rule.organization_id == organization.id).limit(1)).first():
        loader = PulseBenchmarkLoader()
        loader.load_all(session, organization.id)

    benchmark = session.exec(select(Benchmark).limit(1)).first()
    if not benchmark:
        return

    rule_ids = [rule.id for rule in session.exec(select(Rule).where(Rule.organization_id == organization.id).limit(5))]
    if not session.exec(select(RuleGroup).where(RuleGroup.organization_id == organization.id).limit(1)).first():
        group = RuleGroup(
            organization_id=organization.id,
            name="Baseline Controls",
            benchmark_id=benchmark.id,
            description="All seeded development rules",
            rule_ids_json=json.dumps(rule_ids),
            default_hostname="web-01",
            tags_json=json.dumps(["baseline", "seed"]),
        )
        session.add(group)
        session.commit()
    else:
        group = session.exec(select(RuleGroup).where(RuleGroup.organization_id == organization.id)).first()

    if not group:
        return

    if not session.exec(select(Schedule).where(Schedule.organization_id == organization.id).limit(1)).first():
        schedule = Schedule(
            organization_id=organization.id,
            name="Daily Baseline",
            group_id=group.id,
            frequency="daily",
            interval_minutes=1440,
            next_run=datetime.utcnow() + timedelta(days=1),
        )
        session.add(schedule)
        session.commit()

    if session.exec(select(Scan).where(Scan.organization_id == organization.id).limit(1)).first():
        return

    now = datetime.utcnow()
    ai_payload_success = {
        "summary": "All baseline controls passed",
        "key_findings": ["All seeded rules succeeded"],
        "remediations": ["Continue monitoring daily"],
    }
    scan_success = Scan(
        organization_id=organization.id,
        hostname="web-01",
        benchmark_id=benchmark.id,
        group_id=group.id,
        organization_id=organization_id,
        status="passed",
        severity="medium",
        tags_json=json.dumps(["ssh", "baseline"]),
        started_at=now - timedelta(hours=4),
        completed_at=now - timedelta(hours=4) + timedelta(minutes=2),
        last_run=now - timedelta(hours=4) + timedelta(minutes=2),
        total_rules=len(rule_ids),
        passed_rules=len(rule_ids),
        output_path="/tmp/scan-success.json",
        summary=ai_payload_success["summary"],
        ai_summary_json=json.dumps(ai_payload_success),
        triggered_by="seed",
        compliance_score=100.0,
    )
    ai_payload_failed = {
        "summary": "Two controls failed",
        "key_findings": ["pkg-001 failed", "svc-004 failed"],
        "remediations": ["Install missing packages", "Enable auditd"],
    }
    scan_failed = Scan(
        organization_id=organization.id,
        hostname="db-01",
        benchmark_id=benchmark.id,
        group_id=group.id,
        organization_id=organization_id,
        status="failed",
        severity="high",
        tags_json=json.dumps(["audit", "policy"]),
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=2) + timedelta(minutes=3),
        last_run=now - timedelta(hours=2) + timedelta(minutes=3),
        total_rules=len(rule_ids),
        passed_rules=max(len(rule_ids) - 2, 1),
        output_path="/tmp/scan-failed.json",
        summary=ai_payload_failed["summary"],
        ai_summary_json=json.dumps(ai_payload_failed),
        triggered_by="seed",
        compliance_score=33.3,
    )
    session.add(scan_success)
    session.add(scan_failed)
    session.commit()

    report_success = Report(
        organization_id=organization.id,
        scan_id=scan_success.id,
        benchmark_id=benchmark.id,
        organization_id=organizations[0].id if organizations else None,
        hostname=scan_success.hostname,
        score=100.0,
        summary=ai_payload_success["summary"],
        status="passed",
        severity="medium",
        tags_json=scan_success.tags_json,
        output_path="/tmp/report-success.json",
        last_run=scan_success.last_run,
        key_findings_json=json.dumps(ai_payload_success["key_findings"]),
        remediations_json=json.dumps(ai_payload_success["remediations"]),
    )
    report_failed = Report(
        organization_id=organization.id,
        scan_id=scan_failed.id,
        benchmark_id=benchmark.id,
        organization_id=organizations[0].id if organizations else None,
        hostname=scan_failed.hostname,
        score=33.3,
        summary=ai_payload_failed["summary"],
        status="attention",
        severity="high",
        tags_json=scan_failed.tags_json,
        output_path="/tmp/report-failed.json",
        last_run=scan_failed.last_run,
        key_findings_json=json.dumps(ai_payload_failed["key_findings"]),
        remediations_json=json.dumps(ai_payload_failed["remediations"]),
    )
    session.add(report_success)
    session.add(report_failed)
    session.commit()


def _seed_platform_entities(session: Session) -> None:
    organizations = session.exec(select(Organization)).all()
    if not organizations:
        now = datetime.utcnow()
        org_payloads = [
            {
                "name": "CompliancePulse Cloud",
                "slug": "compliancepulse-cloud",
                "plan_tier": "enterprise",
                "seat_limit": 25,
                "subscription_status": "active",
                "subscription_renews_at": now + timedelta(days=30),
                "stripe_customer_id": "cus_dev_cloud",
                "stripe_subscription_id": "sub_dev_cloud",
            },
            {
                "name": "Acme Industries",
                "slug": "acme-industries",
                "plan_tier": "team",
                "seat_limit": 10,
                "subscription_status": "trialing",
                "subscription_renews_at": now + timedelta(days=14),
                "stripe_customer_id": "cus_acme",
                "stripe_subscription_id": "sub_acme",
            },
        ]
        for payload in org_payloads:
            session.add(Organization(**payload))
        session.commit()
        organizations = session.exec(select(Organization)).all()

    users = session.exec(select(User)).all()
    if not users:
        users_to_create = [
            {
                "email": "superadmin@compliancepulse.io",
                "full_name": "Super Admin",
                "hashed_password": "dev-super-admin",
                "super_admin": True,
            },
            {
                "email": "ops@acme.io",
                "full_name": "Operations Admin",
                "hashed_password": "dev-admin",
            },
            {
                "email": "analyst@acme.io",
                "full_name": "Security Analyst",
                "hashed_password": "dev-analyst",
            },
        ]
        for payload in users_to_create:
            session.add(User(**payload))
        session.commit()
        users = session.exec(select(User)).all()

    if organizations and users:
        has_members = session.exec(select(OrganizationMembership).limit(1)).first()
        if not has_members:
            for user in users:
                role = "OWNER" if user.super_admin else "MEMBER"
                session.add(
                    OrganizationMembership(
                        organization_id=organizations[0].id,
                        user_id=user.id,
                        role=role,
                    )
                )
            if len(organizations) > 1 and len(users) > 1:
                session.add(
                    OrganizationMembership(
                        organization_id=organizations[1].id,
                        user_id=users[1].id,
                        role="ADMIN",
                    )
                )
            session.commit()

    if organizations:
        has_flags = session.exec(select(FeatureFlag).limit(1)).first()
        if not has_flags:
            session.add_all(
                [
                    FeatureFlag(key="ai_summaries", description="Enable AI powered report summaries", enabled=True),
                    FeatureFlag(key="governance_mode", description="Require approvals before scans", enabled=False),
                    FeatureFlag(key="fisma_controls", description="Expose beta FISMA mappings", enabled=False),
                ]
            )
            session.commit()

    if organizations:
        has_logs = session.exec(select(PlatformLog).limit(1)).first()
        if not has_logs:
            session.add_all(
                [
                    PlatformLog(level="info", source="scheduler", message="Daily scan schedule executed", details_json=json.dumps({"organization": organizations[0].slug})),
                    PlatformLog(level="warning", source="worker", message="Worker queue depth exceeded threshold", details_json=json.dumps({"pending_jobs": 7})),
                    PlatformLog(level="info", source="billing", message="Stripe webhook processed", details_json=json.dumps({"customer": organizations[0].stripe_customer_id})),
                ]
            )
            session.commit()

    has_workers = session.exec(select(WorkerStatus).limit(1)).first()
    if not has_workers:
        session.add_all(
            [
                WorkerStatus(worker_type="scheduler", status="running", queue_depth=0),
                WorkerStatus(worker_type="scan-worker", status="idle", queue_depth=1),
            ]
        )
        session.commit()

    super_admin = session.exec(select(User).where(User.super_admin == True)).first()  # noqa: E712
    if super_admin and not super_admin.password_reset_token:
        super_admin.password_reset_token = token_urlsafe(16)
        super_admin.password_reset_requested_at = datetime.utcnow()
        session.add(super_admin)
        session.commit()
