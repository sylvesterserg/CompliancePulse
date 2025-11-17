import pytest
from sqlmodel import Session

from app.models import Benchmark, Organization, Rule
from app.schemas import ScanRequest
from app.services.scan_service import ScanService


def _seed_benchmark(session: Session, organization_id: int) -> Benchmark:
    benchmark = Benchmark(
        id="rocky-test",
        title="Rocky Test Benchmark",
        description="",
        version="1.0",
        os_target="rocky-linux-9",
        maintainer="QA",
        source="unit-test",
    )
    session.add(benchmark)

    rules = [
        Rule(
            id="rule-pass",
            organization_id=organization_id,
            benchmark_id=benchmark.id,
            title="Pass rule",
            description="",
            severity="low",
            remediation="",
            check_type="shell",
            command="printf pass",
            expect_type="contains",
            expect_value="pass",
            timeout_seconds=5,
        ),
        Rule(
            id="rule-fail",
            organization_id=organization_id,
            benchmark_id=benchmark.id,
            title="Fail rule",
            description="",
            severity="medium",
            remediation="",
            check_type="shell",
            command="printf fail",
            expect_type="equals",
            expect_value="pass",
            timeout_seconds=5,
        ),
    ]
    for rule in rules:
        session.add(rule)
    session.commit()
    return benchmark


def test_start_scan_persists_results_and_reports(session: Session) -> None:
    org = Organization(name="QA Org", slug="qa-org")
    session.add(org)
    session.commit()
    benchmark = _seed_benchmark(session, org.id)
    service = ScanService(session, organization_id=org.id)

    detail = service.start_scan(
        ScanRequest(hostname="web-01", ip="10.0.0.5", benchmark_id=benchmark.id)
    )

    assert detail.status == "completed"
    assert detail.total_rules == 2
    assert detail.passed_rules == 1
    assert len(detail.results) == 2
    assert {result.rule_id for result in detail.results} == {"rule-pass", "rule-fail"}
    assert detail.summary == "1 of 2 controls require attention."

    reports = service.list_reports()
    assert len(reports) == 1
    assert reports[0].score == pytest.approx(33.33, rel=1e-2)
    assert reports[0].key_findings

    report = service.get_report_for_scan(detail.id)
    assert report.scan_id == detail.id
    assert report.remediations


def test_list_and_get_scan_views(session: Session) -> None:
    org = Organization(name="QA Org 2", slug="qa-org-2")
    session.add(org)
    session.commit()
    benchmark = _seed_benchmark(session, org.id)
    service = ScanService(session, organization_id=org.id)

    created = service.start_scan(ScanRequest(hostname="db-01", benchmark_id=benchmark.id))

    scans = service.list_scans()
    assert len(scans) == 1
    assert scans[0].id == created.id
    assert scans[0].triggered_by == "api"

    fetched = service.get_scan(created.id)
    assert fetched.hostname == "db-01"
    assert len(fetched.results) == 2


def test_start_scan_requires_existing_benchmark(session: Session) -> None:
    org = Organization(name="Empty Org", slug="empty-org")
    session.add(org)
    session.commit()
    service = ScanService(session, organization_id=org.id)

    with pytest.raises(ValueError):
        service.start_scan(ScanRequest(hostname="missing", benchmark_id="unknown"))
