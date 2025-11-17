from __future__ import annotations

import json
from typing import List

from sqlmodel import Session, select

from ..models import Benchmark, Report, Rule, RuleGroup, Scan, ScanJob, ScanResult
from ..schemas import (
    ReportView,
    ScanDetail,
    ScanJobView,
    ScanRequest,
    ScanResultView,
    ScanSummary,
)
from engine.scan_executor import ScanExecutor


class ScanService:
    def __init__(self, session: Session, executor: ScanExecutor | None = None):
        self.session = session
        self.executor = executor or ScanExecutor(session)

    def start_scan(self, request: ScanRequest) -> ScanDetail:
        benchmark = self.session.get(Benchmark, request.benchmark_id)
        if not benchmark:
            raise ValueError(f"Benchmark '{request.benchmark_id}' not found")
        rules = self.session.exec(select(Rule).where(Rule.benchmark_id == request.benchmark_id)).all()
        result = self.executor.run_for_rules(
            hostname=request.hostname,
            ip=request.ip,
            benchmark_id=benchmark.id,
            rules=rules,
            triggered_by="api",
            extra_tags=request.tags,
            organization_id=request.organization_id,
        )
        return self._build_scan_detail(result.scan, result.results)

    def list_scans(self) -> List[ScanSummary]:
        scans = self.session.exec(select(Scan).order_by(Scan.started_at.desc())).all()
        return [self._build_scan_summary(scan) for scan in scans]

    def get_scan(self, scan_id: int) -> ScanDetail:
        scan = self.session.get(Scan, scan_id)
        if not scan:
            raise ValueError("Scan not found")
        results = self._load_results(scan_id)
        return self._build_scan_detail(scan, results)

    def list_reports(self) -> List[ReportView]:
        reports = self.session.exec(select(Report).order_by(Report.created_at.desc())).all()
        return [self._build_report_view(report) for report in reports]

    def get_report(self, report_id: int) -> ReportView:
        report = self.session.get(Report, report_id)
        if not report:
            raise ValueError("Report not found")
        return self._build_report_view(report)

    def get_report_for_scan(self, scan_id: int) -> ReportView:
        report = self.session.exec(select(Report).where(Report.scan_id == scan_id)).first()
        if not report:
            raise ValueError("Report not found for scan")
        return self._build_report_view(report)

    def enqueue_group_scan(self, group_id: int, hostname: str | None = None, triggered_by: str = "manual") -> ScanJobView:
        group = self.session.get(RuleGroup, group_id)
        if not group:
            raise ValueError("Rule group not found")
        job = ScanJob(
            group_id=group.id,
            hostname=hostname or group.default_hostname,
            triggered_by=triggered_by,
            status="pending",
            organization_id=group.organization_id,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return self._build_job_view(job)

    def _build_scan_summary(self, scan: Scan) -> ScanSummary:
        tags = json.loads(scan.tags_json or "[]")
        result = "running"
        if scan.completed_at:
            result = "passed" if scan.passed_rules == scan.total_rules else "failed"
        return ScanSummary(
            id=scan.id,
            hostname=scan.hostname,
            benchmark_id=scan.benchmark_id,
            group_id=scan.group_id,
            status=scan.status,
            result=result,
            severity=scan.severity,
            started_at=scan.started_at,
            completed_at=scan.completed_at,
            last_run=scan.last_run,
            total_rules=scan.total_rules,
            passed_rules=scan.passed_rules,
            compliance_score=scan.compliance_score,
            summary=scan.summary,
            triggered_by=scan.triggered_by,
            tags=tags,
            output_path=scan.output_path,
            organization_id=scan.organization_id,
        )

    def _build_scan_detail(self, scan: Scan, results: List[ScanResult]) -> ScanDetail:
        return ScanDetail(
            **self._build_scan_summary(scan).model_dump(),
            ip=scan.ip,
            results=[self._build_result_view(result) for result in results],
            ai_summary=json.loads(scan.ai_summary_json or "{}"),
        )

    def _build_result_view(self, result: ScanResult) -> ScanResultView:
        return ScanResultView(
            id=result.id,
            rule_id=result.rule_id,
            rule_title=result.rule_title,
            severity=result.severity,
            status=result.status,
            passed=result.passed,
            stdout=result.stdout,
            stderr=result.stderr,
            details=json.loads(result.details_json or "{}"),
            executed_at=result.executed_at,
            completed_at=result.completed_at,
            runtime_ms=result.runtime_ms,
        )

    def _build_report_view(self, report: Report) -> ReportView:
        tags = json.loads(report.tags_json or "[]")
        return ReportView(
            id=report.id,
            scan_id=report.scan_id,
            benchmark_id=report.benchmark_id,
            hostname=report.hostname,
            score=report.score,
            summary=report.summary,
            key_findings=json.loads(report.key_findings_json or "[]"),
            remediations=json.loads(report.remediations_json or "[]"),
            status=report.status,
            severity=report.severity,
            tags=tags,
            output_path=report.output_path,
            last_run=report.last_run,
            created_at=report.created_at,
            organization_id=report.organization_id,
        )

    def _build_job_view(self, job: ScanJob) -> ScanJobView:
        return ScanJobView(
            id=job.id,
            group_id=job.group_id,
            hostname=job.hostname,
            schedule_id=job.schedule_id,
            triggered_by=job.triggered_by,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            organization_id=job.organization_id,
        )

    def _load_results(self, scan_id: int) -> List[ScanResult]:
        return self.session.exec(select(ScanResult).where(ScanResult.scan_id == scan_id)).all()
