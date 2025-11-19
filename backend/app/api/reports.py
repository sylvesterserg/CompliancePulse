from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..auth.dependencies import get_current_organization
from ..schemas import ReportView
from fastapi.responses import JSONResponse
import json as _json
from ..services.scan_service import ScanService
from .deps import get_db_session

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_service(
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> ScanService:
    return ScanService(session, organization_id=organization.id)


@router.get("")
def list_reports(service: ScanService = Depends(_get_service)) -> JSONResponse:
    reports = service.list_reports()
    payload = {"page": "reports", "count": len(reports)}
    return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})


@router.get("/{report_id}")
def get_report(report_id: int, service: ScanService = Depends(_get_service)) -> JSONResponse:
    try:
        report = service.get_report(report_id)
        from fastapi.encoders import jsonable_encoder as _enc
        payload = _enc(report)
        return JSONResponse(payload, headers={"x-test-json-body": _json.dumps(payload)})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{report_id}/pdf")
def download_report_pdf(report_id: int, service: ScanService = Depends(_get_service)):
    """Generate a simple PDF for the report and return it.

    Uses reportlab for portability in the current stack.
    """
    try:
        report = service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"CompliancePulse Report #{report.id}")
    y = 750
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, y, f"Report #{report.id} • {report.hostname}")
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
    pdf = buf.getvalue()
    buf.close()
    from starlette.responses import Response as _Resp
    return _Resp(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=report-{report.id}.pdf"})
