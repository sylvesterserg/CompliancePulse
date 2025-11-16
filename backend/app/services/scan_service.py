from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from sqlmodel import Session, select

from ..config import settings
from ..models import Benchmark, Report, Rule, RuleResult, Scan
from ..schemas import ReportView, RuleResultView, ScanDetail, ScanRequest, ScanSummary
from .rule_engine import RuleExecutionEngine

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class ScanService:
    def __init__(self, session: Session):
        self.session = session
        self.rule_engine = RuleExecutionEngine()
        for path in (settings.logs_dir, settings.artifacts_dir):
            Path(path).mkdir(parents=True, exist_ok=True)

    def start_scan(self, request: ScanRequest) -> ScanDetail:
        benchmark = self.session.get(Benchmark, request.benchmark_id)
        if not benchmark:
            raise ValueError(f"Benchmark '{request.benchmark_id}' not found")
        rules = self.session.exec(
            select(Rule).where(Rule.benchmark_id == request.benchmark_id)
        ).all()
        requested_tags = set(getattr(request, "tags", []) or [])
        scan_tags = sorted(requested_tags | set(self._collect_rule_tags(rules)))
        scan_severity = self._derive_scan_severity(rules)
        scan = Scan(
            hostname=request.hostname,
            ip=request.ip,
            benchmark_id=request.benchmark_id,
            status="running",
            started_at=datetime.utcnow(),
            total_rules=len(rules),
            tags_json=json.dumps(scan_tags),
            severity=scan_severity,
        )
        self.session.add(scan)
        self.session.commit()
        self.session.refresh(scan)
        results: List[RuleResult] = []
        passed_count = 0
        for rule in rules:
            execution = self.rule_engine.execute(rule)
            rule_result = RuleResult(
                scan_id=scan.id,
                rule_id=rule.id,
                status="passed" if execution.passed else "failed",
                passed=execution.passed,
                stdout=execution.stdout,
                stderr=execution.stderr,
                expectation_detail=execution.expectation_detail,
                completed_at=datetime.utcnow(),
            )
            self.session.add(rule_result)
            self.session.commit()
            self.session.refresh(rule_result)
            results.append(rule_result)
            rule.last_run = datetime.utcnow()
            self.session.add(rule)
            if execution.passed:
                passed_count += 1
        scan.completed_at = datetime.utcnow()
        scan.last_run = scan.completed_at
        scan.status = "completed"
        scan.passed_rules = passed_count
        scan.total_rules = len(rules)
        self.session.add(scan)
        score = 0.0
        if scan.total_rules:
            score = round((scan.passed_rules / scan.total_rules) * 100, 2)
        summary = f"{scan.passed_rules}/{scan.total_rules} rules passed"
        report = Report(
            scan_id=scan.id,
            benchmark_id=scan.benchmark_id,
            hostname=scan.hostname,
            score=score,
            summary=summary,
            status="passed" if passed_count == len(rules) else "attention",
            severity=scan.severity,
            tags_json=scan.tags_json,
            last_run=scan.completed_at,
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        self.session.refresh(scan)
        scan.output_path = str(self._write_scan_artifact(scan, results))
        report.output_path = str(self._write_report_artifact(report, scan))
        self.session.add(scan)
        self.session.add(report)
        self.session.commit()
        return self._build_scan_detail(scan, results)

    def list_scans(self) -> List[ScanSummary]:
        scans = self.session.exec(select(Scan).order_by(Scan.started_at.desc())).all()
        return [self._build_scan_summary(scan) for scan in scans]

    def get_scan(self, scan_id: int) -> ScanDetail:
        scan = self.session.get(Scan, scan_id)
        if not scan:
            raise ValueError("Scan not found")
        results = self.session.exec(
            select(RuleResult).where(RuleResult.scan_id == scan_id)
        ).all()
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

    def _build_scan_summary(self, scan: Scan) -> ScanSummary:
        tags = json.loads(scan.tags_json or "[]")
        result = "running"
        if scan.completed_at:
            result = "passed" if scan.passed_rules == scan.total_rules else "failed"
        return ScanSummary(
            id=scan.id,
            hostname=scan.hostname,
            benchmark_id=scan.benchmark_id,
            status=scan.status,
            result=result,
            severity=scan.severity,
            started_at=scan.started_at,
            completed_at=scan.completed_at,
            last_run=scan.last_run,
            total_rules=scan.total_rules,
            passed_rules=scan.passed_rules,
            tags=tags,
            output_path=scan.output_path,
        )

    def _build_scan_detail(self, scan: Scan, results: List[RuleResult]) -> ScanDetail:
        return ScanDetail(
            **self._build_scan_summary(scan).model_dump(),
            ip=scan.ip,
            results=[self._build_rule_result_view(result) for result in results],
        )

    def _build_rule_result_view(self, result: RuleResult) -> RuleResultView:
        return RuleResultView(
            id=result.id,
            rule_id=result.rule_id,
            status=result.status,
            passed=result.passed,
            stdout=result.stdout,
            stderr=result.stderr,
            expectation_detail=result.expectation_detail,
            created_at=result.created_at,
            completed_at=result.completed_at,
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
            status=report.status,
            severity=report.severity,
            tags=tags,
            output_path=report.output_path,
            last_run=report.last_run,
            created_at=report.created_at,
        )

    def _derive_scan_severity(self, rules: List[Rule]) -> str:
        highest = "info"
        for rule in rules:
            severity = rule.severity.lower()
            if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(highest, 0):
                highest = severity
        return highest

    def _collect_rule_tags(self, rules: List[Rule]) -> List[str]:
        tag_set = set()
        for rule in rules:
            for tag in json.loads(rule.tags_json or "[]"):
                tag_set.add(tag)
        return sorted(tag_set)

    def _write_scan_artifact(self, scan: Scan, results: List[RuleResult]) -> Path:
        path = Path(settings.logs_dir) / f"scan_{scan.id}.json"
        payload = {
            "scan": self._build_scan_summary(scan).model_dump(),
            "results": [self._build_rule_result_view(result).model_dump() for result in results],
        }
        payload["scan"]["output_path"] = str(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        return path

    def _write_report_artifact(self, report: Report, scan: Scan) -> Path:
        path = Path(settings.artifacts_dir) / f"report_{report.id}.json"
        payload = {
            "report": self._build_report_view(report).model_dump(),
            "scan": self._build_scan_summary(scan).model_dump(),
        }
        payload["report"]["output_path"] = str(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        return path
