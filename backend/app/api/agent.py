from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..auth.dependencies import require_authenticated_user
from ..config import settings
from .deps import get_db_session

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_authenticated_user)])


@router.post("/upload")
async def agent_upload(request: Request, session: Session = Depends(get_db_session)) -> JSONResponse:
    """Accept a JSON payload from a lightweight agent and store it to disk.

    - Stores raw JSON under artifacts/agent/{yyyy-mm-dd}/upload-<ts>.json
    - Returns {stored: true, path: relative_path}
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    day = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(settings.artifacts_dir) / "agent" / day
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%H%M%S")
    out_file = out_dir / f"upload-{ts}.json"
    out_file.write_text(json.dumps(payload, indent=2))
    rel_path = str(out_file.relative_to(settings.artifacts_dir))
    body = {"stored": True, "path": rel_path}
    return JSONResponse(body, headers={"x-test-json-body": json.dumps(body)})

