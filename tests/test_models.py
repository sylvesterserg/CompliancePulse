import json
import uuid

import pytest
from sqlmodel import select

from backend.app.models import Benchmark, Report, Rule
from backend.app.schemas import ReportView, RuleDetail, ScanRequest
from backend.app.services.scan_service import ScanService


def test_rule_model_round_trip(session, auth_context):
    benchmark = session.exec(select(Benchmark)).first()
    assert benchmark, "Seed benchmark must exist for model tests"
    rule_id = f"test-rule-{uuid.uuid4().hex[:8]}"
    rule = Rule(
        id=rule_id,
        organization_id=auth_context["org_id"],
        benchmark_id=benchmark.id,
        title="Ensure temporary rule works",
        description="Synthetic rule for persistence testing",
        severity="high",
        remediation="noop",
        references_json=json.dumps(["CIS-0.0"]),
        metadata_json=json.dumps({"tags": ["unit-test"]}),
        check_type="shell",
        command="/bin/true",
        expect_type="exit_code",
        expect_value="0",
        timeout_seconds=5,
    )
    session.add(rule)
    session.commit()
    reloaded = session.get(Rule, rule_id)
    assert reloaded is not None
    assert reloaded.severity == "high"
    assert json.loads(reloaded.metadata_json)["tags"] == ["unit-test"]


def test_scan_and_report_persistence(session, auth_context):
    benchmark = session.exec(select(Benchmark)).first()
    request = ScanRequest(hostname="model-host", ip="203.0.113.10", benchmark_id=benchmark.id)
    service = ScanService(session, organization_id=auth_context["org_id"])
    detail = service.start_scan(request)
    assert detail.status == "completed"
    assert detail.results
    report = session.exec(select(Report).where(Report.scan_id == detail.id)).first()
    assert report is not None
    assert report.score >= 0


def test_schema_validation_matches_models(session, sample_data_factory):
    sample = sample_data_factory(hostname="schema-host", score=88.0)
    report: Report = sample["report"]  # type: ignore[assignment]
    rule = session.exec(select(Rule)).first()
    schema = RuleDetail(
        id=rule.id,
        benchmark_id=rule.benchmark_id,
        title=rule.title,
        severity=rule.severity,
        description=rule.description,
        remediation=rule.remediation,
        references=json.loads(rule.references_json),
        metadata=json.loads(rule.metadata_json),
        check_type=rule.check_type,
        command=rule.command,
        expect_type=rule.expect_type,
        expect_value=rule.expect_value,
        timeout_seconds=rule.timeout_seconds,
    )
    assert schema.severity == rule.severity
    report_view = ReportView(
        id=report.id,
        scan_id=report.scan_id,
        benchmark_id=report.benchmark_id,
        hostname=report.hostname,
        score=report.score,
        summary=report.summary,
        created_at=report.created_at,
    )
    assert report_view.hostname == "schema-host"
    assert report_view.score == pytest.approx(88.0)
