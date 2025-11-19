from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

from sqlmodel import Session, select
import logging

try:  # dual import roots for tests vs runtime
    from app.config import settings  # type: ignore
    from app.models import Report, Rule, RuleGroup, Scan, ScanJob, ScanResult  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.config import settings  # type: ignore
    from backend.app.models import (  # type: ignore
        Report,
        Rule,
        RuleGroup,
        Scan,
        ScanJob,
        ScanResult,
    )

from .ai_summary import summarize_scan
from .rule_engine import RuleEngine, RuleEvaluation

SEVERITY_WEIGHTS = {"info": 1, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class ScanExecutionResult:
    scan: Scan
    results: List[ScanResult]
    report: Report


logger = logging.getLogger("compliancepulse.engine")


class ScanExecutor:
    def __init__(self, session: Session, organization_id: int, rule_engine: RuleEngine | None = None):
        self.session = session
        self.organization_id = organization_id
        self.rule_engine = rule_engine or RuleEngine()
        for path in (settings.logs_dir, settings.artifacts_dir):
            Path(path).mkdir(parents=True, exist_ok=True)

    def run_for_rules(
        self,
        hostname: str,
        ip: str | None,
        benchmark_id: str,
        rules: Sequence[Rule],
        triggered_by: str = "manual",
        group: RuleGroup | None = None,
        extra_tags: Sequence[str] | None = None,
    ) -> ScanExecutionResult:
        rules = list(rules)
        tags = self._collect_rule_tags(rules)
        if extra_tags:
            tags = sorted(set(tags) | set(extra_tags))
        severity = self._derive_severity(rules)
        scan = Scan(
            organization_id=self.organization_id,
            hostname=hostname,
            ip=ip,
            benchmark_id=benchmark_id,
            group_id=group.id if group else None,
            status="running",
            severity=severity,
            tags_json=json.dumps(tags),
            started_at=datetime.utcnow(),
            triggered_by=triggered_by,
            total_rules=len(rules),
        )
        self.session.add(scan)
        self.session.commit()
        self.session.refresh(scan)

        results: List[ScanResult] = []
        passed_rules = 0
        weighted_pass = 0
        weighted_total = 0

        for rule in rules:
            evaluation = self.rule_engine.evaluate(rule)
            result_model = self._persist_result(scan, rule, evaluation)
            results.append(result_model)
            if evaluation.passed:
                passed_rules += 1
                weighted_pass += SEVERITY_WEIGHTS.get(rule.severity.lower(), 1)
            weighted_total += SEVERITY_WEIGHTS.get(rule.severity.lower(), 1)

        score = 0.0
        if weighted_total:
            score = round((weighted_pass / weighted_total) * 100, 2)

        summary_bundle = summarize_scan(results)
        scan.completed_at = datetime.utcnow()
        scan.last_run = scan.completed_at
        scan.status = "completed"
        scan.passed_rules = passed_rules
        scan.total_rules = len(rules)
        scan.summary = summary_bundle.get("summary")
        scan.ai_summary_json = json.dumps(summary_bundle)
        scan.compliance_score = score
        self.session.add(scan)

        total = len(rules)
        status = "passed" if total and passed_rules == total else "attention"
        report = Report(
            organization_id=self.organization_id,
            scan_id=scan.id,
            benchmark_id=scan.benchmark_id,
            hostname=scan.hostname,
            score=score,
            summary=summary_bundle.get("summary", ""),
            status=status,
            severity=scan.severity,
            tags_json=scan.tags_json,
            last_run=scan.completed_at,
            key_findings_json=json.dumps(summary_bundle.get("key_findings", [])),
            remediations_json=json.dumps(summary_bundle.get("remediations", [])),
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        self.session.refresh(scan)

        self._write_artifacts(scan, results, report)

        if group:
            group.last_run = scan.completed_at
            self.session.add(group)
            self.session.commit()

        return ScanExecutionResult(scan=scan, results=results, report=report)

    def run_for_group(
        self,
        group_id: int,
        hostname: str | None = None,
        ip: str | None = None,
        triggered_by: str = "automation",
    ) -> ScanExecutionResult:
        group = self.session.get(RuleGroup, group_id)
        if not group:
            raise ValueError("Rule group not found")
        if group.organization_id != self.organization_id:
            raise ValueError("Unauthorized access to group")
        rule_ids = self._group_rule_ids(group)
        if rule_ids:
            rules = self.session.exec(select(Rule).where(Rule.id.in_(rule_ids))).all()
        else:
            rules = self.session.exec(select(Rule).where(Rule.benchmark_id == group.benchmark_id)).all()
        return self.run_for_rules(
            hostname=hostname or group.default_hostname,
            ip=ip or group.default_ip,
            benchmark_id=group.benchmark_id,
            rules=rules,
            triggered_by=triggered_by,
            group=group,
            extra_tags=json.loads(group.tags_json or "[]"),
        )

    def execute_job(self, job: ScanJob) -> ScanExecutionResult:
        if job.organization_id != self.organization_id:
            raise ValueError("Job organization mismatch")
        return self.run_for_group(
            group_id=job.group_id,
            hostname=job.hostname,
            triggered_by=job.triggered_by,
        )

    def _collect_rule_tags(self, rules: Iterable[Rule]) -> List[str]:
        tag_set: set[str] = set()
        for rule in rules:
            for tag in json.loads(rule.tags_json or "[]"):
                tag_set.add(tag)
        return sorted(tag_set)

    def _derive_severity(self, rules: Iterable[Rule]) -> str:
        highest = "info"
        for rule in rules:
            severity = rule.severity.lower()
            if SEVERITY_WEIGHTS.get(severity, 0) > SEVERITY_WEIGHTS.get(highest, 0):
                highest = severity
        return highest

    def _group_rule_ids(self, group: RuleGroup) -> List[str]:
        try:
            return json.loads(group.rule_ids_json or "[]")
        except json.JSONDecodeError:
            return []

    def _persist_result(self, scan: Scan, rule: Rule, evaluation: RuleEvaluation) -> ScanResult:
        result = ScanResult(
            organization_id=self.organization_id,
            scan_id=scan.id,
            rule_id=rule.id,
            rule_title=rule.title,
            severity=rule.severity,
            status="passed" if evaluation.passed else "failed",
            passed=evaluation.passed,
            stdout=evaluation.stdout,
            stderr=evaluation.stderr,
            details_json=json.dumps(evaluation.details),
            executed_at=evaluation.started_at,
            completed_at=evaluation.completed_at,
            runtime_ms=evaluation.runtime_ms,
        )
        self.session.add(result)
        self.session.flush()
        rule.last_run = evaluation.completed_at
        self.session.add(rule)
        return result

    def _write_artifacts(self, scan: Scan, results: List[ScanResult], report: Report) -> None:
        scan_payload = {
            "scan": {
                "id": scan.id,
                "hostname": scan.hostname,
                "benchmark_id": scan.benchmark_id,
                "group_id": scan.group_id,
                "status": scan.status,
                "severity": scan.severity,
                "started_at": scan.started_at.isoformat() if scan.started_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                "total_rules": scan.total_rules,
                "passed_rules": scan.passed_rules,
                "tags": json.loads(scan.tags_json or "[]"),
                "summary": scan.summary,
                "ai_summary": json.loads(scan.ai_summary_json or "{}"),
                "output_path": scan.output_path,
            },
            "results": [
                {
                    "id": result.id,
                    "rule_id": result.rule_id,
                    "rule_title": result.rule_title,
                    "status": result.status,
                    "passed": result.passed,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "details": json.loads(result.details_json or "{}"),
                }
                for result in results
            ],
        }
        scan_path = Path(settings.logs_dir) / f"scan_{scan.id}.json"
        scan_path.write_text(json.dumps(scan_payload, indent=2, default=str), encoding="utf-8")
        scan_payload["scan"]["output_path"] = str(scan_path)
        scan.output_path = str(scan_path)

        report_payload = {
            "report": {
                "id": report.id,
                "scan_id": report.scan_id,
                "score": report.score,
                "summary": report.summary,
                "key_findings": json.loads(report.key_findings_json or "[]"),
                "remediations": json.loads(report.remediations_json or "[]"),
                "output_path": report.output_path,
            },
            "scan": scan_payload["scan"],
        }
        # JSON artifact
        report_path = Path(settings.artifacts_dir) / f"report_{report.id}.json"
        report_path.write_text(json.dumps(report_payload, indent=2, default=str), encoding="utf-8")
        report_payload["report"]["output_path"] = str(report_path)
        report.output_path = str(report_path)
        # Best-effort HTML artifact
        try:
            html_path = Path(settings.artifacts_dir) / f"report_{report.id}.html"
            html = f"""
<!DOCTYPE html><html><head><meta charset='utf-8'><title>Report #{report.id}</title>
<style>body{{font-family:system-ui,sans-serif;padding:24px}} .meta{{color:#475569;font-size:12px}}</style>
</head><body>
<h1>Report #{report.id} · {scan.hostname}</h1>
<p class='meta'>Benchmark {scan.benchmark_id} · Severity {report.severity} · Score {report.score}%</p>
<h2>Summary</h2>
<p>{report.summary or ''}</p>
</body></html>
"""
            html_path.write_text(html, encoding="utf-8")
        except Exception:  # pragma: no cover - artifact generation should not fail job
            logger.exception("Failed to render HTML artifact for report %s", report.id)
        # Best-effort PDF artifact
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            pdf_path = Path(settings.artifacts_dir) / f"report_{report.id}.pdf"
            c = canvas.Canvas(str(pdf_path), pagesize=letter)
            c.setTitle(f"CompliancePulse Report #{report.id}")
            y = 750
            c.setFont("Helvetica-Bold", 14)
            c.drawString(72, y, f"Report #{report.id} • {scan.hostname}")
            y -= 22
            c.setFont("Helvetica", 11)
            c.drawString(72, y, f"Score: {report.score}%  Status: {report.status}  Severity: {report.severity}")
            y -= 16
            c.drawString(72, y, f"Benchmark: {report.benchmark_id}  Scan: {report.scan_id}")
            y -= 24
            summary = report.summary or ""
            for i in range(0, len(summary), 90):
                c.drawString(72, y, summary[i:i+90])
                y -= 14
            c.showPage()
            c.save()
        except Exception:  # pragma: no cover
            logger.exception("Failed to render PDF artifact for report %s", report.id)

        self.session.add(scan)
        self.session.add(report)
        self.session.commit()
