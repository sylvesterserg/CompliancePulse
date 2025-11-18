from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlmodel import Session, select
import os

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


def seed_bootstrap_admin(session: Session) -> None:
    """Optionally create an initial admin in non-development environments.

    Controlled by environment variables:
      - ADMIN_EMAIL
      - ADMIN_PASSWORD
      - ADMIN_ORG_NAME (default: "Default Organization")
    """
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        return

    existing_user = session.exec(select(User).where(User.email == admin_email.lower())).first()
    if existing_user:
        return

    org_name = os.getenv("ADMIN_ORG_NAME", "Default Organization").strip() or "Default Organization"
    slug = org_name.lower().replace(" ", "-")
    organization = session.exec(select(Organization).where(Organization.slug == slug)).first()
    if not organization:
        organization = Organization(name=org_name, slug=slug)
        session.add(organization)
        session.commit()
        session.refresh(organization)

    user = User(
        email=admin_email.lower(),
        hashed_password=hash_password(admin_password),
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

    # Load baseline content
    loader = PulseBenchmarkLoader()
    loader.load_all(session, organization.id)
