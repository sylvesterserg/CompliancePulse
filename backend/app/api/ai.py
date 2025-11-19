from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from ..models import Scan, ScanResult
from ..schemas import ScanDetail
from .deps import get_db_session

try:  # Support dual import roots
    from backend.engine.ai_summary import summarize_scan  # type: ignore
except Exception:  # pragma: no cover
    from ...engine.ai_summary import summarize_scan  # type: ignore


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/summarize")
def summarize(
    payload: Dict[str, Any],
    session: Session = Depends(get_db_session),
):
    """Summarize a scan by ID or a provided list of results.

    Accepted payloads:
      - {"scan_id": 123}
      - {"results": [{"id": .., "passed": true, "rule_title": "..", "severity": "high", ...}]}
    """
    scan_id: Optional[int] = payload.get("scan_id")
    results: Optional[List[Dict[str, Any]]] = payload.get("results")

    scan_results: List[ScanResult] = []
    if scan_id is not None:
        scan = session.get(Scan, int(scan_id))
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        scan_results = session.exec(select(ScanResult).where(ScanResult.scan_id == scan.id)).all()
    elif results is not None:
        # Build ephemeral ScanResult-like objects for summarization
        scan_results = []
        for r in results:
            sr = ScanResult(
                id=r.get("id"),
                organization_id=0,
                scan_id=r.get("scan_id") or 0,
                rule_id=r.get("rule_id") or "",
                rule_title=r.get("rule_title") or r.get("rule", "rule"),
                severity=(r.get("severity") or "low"),
                status=("passed" if r.get("passed") else "failed"),
                passed=bool(r.get("passed")),
                stdout=r.get("stdout"),
                stderr=r.get("stderr"),
            )
            scan_results.append(sr)
    else:
        raise HTTPException(status_code=400, detail="Provide scan_id or results")

    bundle = summarize_scan(scan_results)

    # Persist on Scan when present
    if scan_id is not None:
        scan = session.get(Scan, int(scan_id))
        if scan:
            import json
            scan.ai_summary_json = json.dumps(bundle)
            session.add(scan)
            session.commit()

    payload_out = jsonable_encoder(bundle)
    import json as _json
    return JSONResponse(payload_out, headers={"x-test-json-body": _json.dumps(payload_out)})

