from __future__ import annotations

import json
from datetime import datetime, timedelta

from secrets import token_urlsafe

from sqlmodel import Session, select

from .config import settings
from .models import (
    Benchmark,
    FeatureFlag,
    Organization,
    OrganizationMembership,
    PlatformLog,
    Report,
    Rule,
    RuleGroup,
    Scan,
    Schedule,
    User,
    WorkerStatus,
)


def seed_dev_data(session: Session) -> None:
    """Populate the database with helpful fixtures for local development."""

    if settings.environment.lower() != "development":
        return
    _seed_platform_entities(session)
    organizations = session.exec(select(Organization).order_by(Organization.created_at)).all()
    organization_id = organizations[0].id if organizations else None

    has_rules = session.exec(select(Rule).limit(1)).first()
    if has_rules:
        return

    benchmark = session.exec(select(Benchmark).limit(1)).first()
    if not benchmark:
        benchmark = Benchmark(
            id="rocky-linux-baseline",
            title="Rocky Linux Baseline",
            description="Base CIS-aligned checks for Rocky Linux",
            version="1.0",
            os_target="Rocky Linux 9",
            maintainer="CompliancePulse",
            source="seed",
            tags_json=json.dumps(["linux", "cis", "baseline"]),
            schema_version="0.4",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(benchmark)
        session.commit()

    rules = [
        {
            "id": "pkg-001",
            "title": "Ensure openssh-clients is installed",
            "severity": "medium",
            "command": "rpm -q openssh-clients",
            "expect": "0",
            "tags": ["ssh", "packages"],
        },
        {
            "id": "svc-004",
            "title": "Auditd service enabled",
            "severity": "high",
            "command": "systemctl is-enabled auditd",
            "expect": "enabled",
            "tags": ["audit", "services"],
        },
        {
            "id": "cfg-010",
            "title": "Password max days is set",
            "severity": "low",
            "command": "grep PASS_MAX_DAYS /etc/login.defs",
            "expect": "PASS_MAX_DAYS   90",
            "tags": ["auth", "policy"],
        },
    ]

    rule_ids = []
    for payload in rules:
        rule_ids.append(payload["id"])
        session.add(
            Rule(
                id=payload["id"],
                benchmark_id=benchmark.id,
                title=payload["title"],
                description=f"Auto-generated rule for {payload['title']}",
                severity=payload["severity"],
                remediation="Follow vendor hardening guidance.",
                references_json=json.dumps(["https://rockylinux.org"]),
                metadata_json=json.dumps({"category": "seed"}),
                tags_json=json.dumps(payload["tags"]),
                check_type="shell",
                command=payload["command"],
                expect_type="contains" if payload["severity"] == "low" else "equals",
                expect_value=payload["expect"],
                timeout_seconds=10,
                status="active",
            )
        )
    session.commit()

    group = RuleGroup(
        name="Baseline Controls",
        benchmark_id=benchmark.id,
        description="All seeded development rules",
        rule_ids_json=json.dumps(rule_ids),
        default_hostname="web-01",
        tags_json=json.dumps(["baseline", "seed"]),
        organization_id=organization_id,
    )
    session.add(group)
    session.commit()

    schedule = Schedule(
        name="Daily Baseline",
        group_id=group.id,
        organization_id=organization_id,
        frequency="daily",
        interval_minutes=1440,
        next_run=datetime.utcnow() + timedelta(days=1),
    )
    session.add(schedule)
    session.commit()

    now = datetime.utcnow()
    ai_payload_success = {
        "summary": "All baseline controls passed",
        "key_findings": ["All seeded rules succeeded"],
        "remediations": ["Continue monitoring daily"],
    }
    scan_success = Scan(
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
        total_rules=3,
        passed_rules=3,
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
        total_rules=3,
        passed_rules=1,
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
