from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..auth.dependencies import require_authenticated_user
from ..models import Benchmark, Rule
from ..schemas import ScanDetail, ScanRequest
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_authenticated_user)])


def _parse_csv(content: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    results: List[Dict[str, Any]] = []
    for row in reader:
        results.append({
            "rule_id": row.get("rule_id") or row.get("id"),
            "rule_title": row.get("title") or row.get("rule_title"),
            "severity": (row.get("severity") or "low").lower(),
            "passed": (str(row.get("passed") or "").strip().lower() in {"1", "true", "yes", "y"}),
            "stdout": row.get("stdout") or "",
            "stderr": row.get("stderr") or "",
        })
    return results


@router.post("/upload")
async def ingest_upload(
    hostname: str | None = None,
    benchmark_id: str | None = None,
    file: UploadFile | None = File(None),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Accept JSON or CSV results and persist a synthetic scan + report.

    Expected fields per record:
      - rule_id, rule_title, severity, passed, stdout, stderr
    """
    items: List[Dict[str, Any]]
    if file is not None:
        if hostname is None or benchmark_id is None:
            raise HTTPException(status_code=400, detail="hostname and benchmark_id required")
        if not session.get(Benchmark, benchmark_id):
            raise HTTPException(status_code=404, detail="Benchmark not found")
        content_bytes = await file.read()
        content_text = content_bytes.decode("utf-8", errors="ignore")
        if file.content_type in ("text/csv", "application/csv") or (file.filename and file.filename.endswith(".csv")):
            items = _parse_csv(content_text)
        else:
            try:
                items = json.loads(content_text)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON or CSV: {exc}") from exc
    else:
        # JSON body fallback: {hostname, benchmark_id, results: [...]}
        raise HTTPException(status_code=415, detail="Multipart upload required")

    # Build a scan based on existing rules for the benchmark.
    # For simplicity, we will create results by matching rule_id and using the provided pass/fail and outputs.
    service = ScanService(session)
    # Trigger an empty scan to allocate entities, then overwrite results
    detail: ScanDetail = service.start_scan(ScanRequest(hostname=hostname, ip=None, benchmark_id=benchmark_id, tags=[]))

    # Overwrite results with uploaded values
    from ..models import ScanResult, Scan
    severities = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    weighted_total = 0
    weighted_pass = 0
    passed_rules = 0

    # Delete any auto-generated results, then insert our own
    session.exec(
        f"DELETE FROM scanresult WHERE scan_id = {detail.id}"
    )  # raw for simplicity in this scoped flow
    session.commit()

    for item in items:
        rid = str(item.get("rule_id") or "").strip()
        rule: Rule | None = session.get(Rule, rid)
        if not rule:
            # create a lightweight placeholder under the benchmark if missing
            rule = Rule(
                id=rid or f"ingest-{detail.id}-{len(items)}",
                organization_id=service.organization_id,
                benchmark_id=benchmark_id,
                title=item.get("rule_title") or rid or "Uploaded Check",
                description="",
                severity=(item.get("severity") or "low").lower(),
                remediation="",
                check_type="shell",
                command="",
                expect_type="equals",
                expect_value="0",
                status="active",
            )
            session.add(rule)
            session.commit()
        sev = (item.get("severity") or rule.severity or "low").lower()
        weight = severities.get(sev, 1)
        passed = bool(item.get("passed"))
        weighted_total += weight
        if passed:
            weighted_pass += weight
            passed_rules += 1
        sr = ScanResult(
            organization_id=service.organization_id,
            scan_id=detail.id,
            rule_id=rule.id,
            rule_title=rule.title,
            severity=sev,
            status=("passed" if passed else "failed"),
            passed=passed,
            stdout=item.get("stdout") or "",
            stderr=item.get("stderr") or "",
        )
        session.add(sr)
    score = round((weighted_pass / weighted_total) * 100, 2) if weighted_total else 0.0
    scan = session.get(Scan, detail.id)
    if scan:
        scan.passed_rules = passed_rules
        scan.total_rules = len(items)
        scan.compliance_score = score
        session.add(scan)
    session.commit()

    refreshed = service.get_scan(detail.id)
    payload = jsonable_encoder(refreshed)
    return JSONResponse(payload, headers={"x-test-json-body": json.dumps(payload)})
