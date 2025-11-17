from sqlmodel import select

from backend.app.models import Benchmark, Report, Rule, Scan
from backend.app.schemas import ScanRequest
from backend.app.services.scan_service import ScanService


def test_seeded_benchmark_contains_expected_rules(session):
    benchmark = session.exec(select(Benchmark)).first()
    assert benchmark is not None
    rules = session.exec(select(Rule).where(Rule.benchmark_id == benchmark.id)).all()
    assert len(rules) >= 3
    assert {rule.severity for rule in rules}


def test_scan_and_report_seed_relationships(session):
    benchmark = session.exec(select(Benchmark)).first()
    service = ScanService(session)
    for idx in range(2):
        request = ScanRequest(
            hostname=f"seed-host-{idx}",
            benchmark_id=benchmark.id,
            ip=f"192.0.2.{10 + idx}",
        )
        service.start_scan(request)
    scans = session.exec(select(Scan)).all()
    reports = session.exec(select(Report)).all()
    assert len(scans) >= 2
    assert len(reports) >= 2
    assert all(scan.started_at is not None for scan in scans)
    assert all(report.created_at is not None for report in reports)
