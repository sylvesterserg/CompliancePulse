"""Tests for the ScanService orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pytest
from sqlmodel import Session

from app.models import Benchmark, Rule
from app.schemas import ScanRequest
from app.services.rule_engine import ExecutionResult
from app.services.scan_service import ScanService


@dataclass
class _StubRuleEngine:
    outcomes: Dict[str, ExecutionResult]

    def execute(self, rule: Rule) -> ExecutionResult:  # pragma: no cover - tiny shim
        return self.outcomes[rule.id]


def _seed_benchmark(session: Session) -> Benchmark:
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
            benchmark_id=benchmark.id,
            title="Pass rule",
            description="",
            severity="low",
            remediation="",
            check_type="shell",
            command="echo pass",
            expect_type="equals",
            expect_value="pass",
            timeout_seconds=5,
        ),
        Rule(
            id="rule-fail",
            benchmark_id=benchmark.id,
            title="Fail rule",
            description="",
            severity="medium",
            remediation="",
            check_type="shell",
            command="echo fail",
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
    benchmark = _seed_benchmark(session)
    service = ScanService(session)
    service.rule_engine = _StubRuleEngine(
        outcomes={
            "rule-pass": ExecutionResult(
                stdout="pass",
                stderr="",
                exit_code=0,
                passed=True,
                expectation_detail="stdout equals 'pass'",
            ),
            "rule-fail": ExecutionResult(
                stdout="fail",
                stderr="",
                exit_code=0,
                passed=False,
                expectation_detail="stdout equals 'pass'",
            ),
        }
    )

    detail = service.start_scan(
        ScanRequest(hostname="web-01", ip="10.0.0.5", benchmark_id=benchmark.id)
    )

    assert detail.status == "completed"
    assert detail.total_rules == 2
    assert detail.passed_rules == 1
    assert len(detail.results) == 2
    assert {result.rule_id for result in detail.results} == {"rule-pass", "rule-fail"}

    reports = service.list_reports()
    assert len(reports) == 1
    assert reports[0].score == 50.0

    report = service.get_report_for_scan(detail.id)
    assert report.scan_id == detail.id


def test_list_and_get_scan_views(session: Session) -> None:
    benchmark = _seed_benchmark(session)
    service = ScanService(session)
    service.rule_engine = _StubRuleEngine(
        outcomes={
            "rule-pass": ExecutionResult(
                stdout="pass",
                stderr="",
                exit_code=0,
                passed=True,
                expectation_detail="stdout equals 'pass'",
            ),
            "rule-fail": ExecutionResult(
                stdout="fail",
                stderr="",
                exit_code=0,
                passed=True,
                expectation_detail="stdout equals 'pass'",
            ),
        }
    )

    created = service.start_scan(ScanRequest(hostname="db-01", benchmark_id=benchmark.id))

    scans = service.list_scans()
    assert len(scans) == 1
    assert scans[0].id == created.id

    fetched = service.get_scan(created.id)
    assert fetched.hostname == "db-01"
    assert len(fetched.results) == 2


def test_start_scan_requires_existing_benchmark(session: Session) -> None:
    service = ScanService(session)

    with pytest.raises(ValueError):
        service.start_scan(ScanRequest(hostname="missing", benchmark_id="unknown"))
