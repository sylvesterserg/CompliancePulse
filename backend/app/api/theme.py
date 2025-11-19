from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..auth.dependencies import get_current_organization, require_authenticated_user, require_role
from ..models import MembershipRole
from ..config import settings
from .deps import get_db_session

router = APIRouter(prefix="/settings/theme", tags=["theme"], dependencies=[Depends(require_authenticated_user)])


def _tenant_dir(org_id: int) -> Path:
    d = Path(settings.frontend_static_dir) / "tenants" / str(org_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/logo", dependencies=[Depends(require_role(MembershipRole.ADMIN))])
async def upload_logo(
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> JSONResponse:
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
        raise HTTPException(status_code=400, detail="Logo must be an image")
    data = await file.read()
    path = _tenant_dir(organization.id) / "logo.png"
    path.write_bytes(data)
    body = {"uploaded": True, "path": f"/static/tenants/{organization.id}/logo.png"}
    import json as _json
    return JSONResponse(body, headers={"x-test-json-body": _json.dumps(body)})


@router.post("/css", dependencies=[Depends(require_role(MembershipRole.ADMIN))])
async def upload_css(
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    organization = Depends(get_current_organization),
) -> JSONResponse:
    if not (file.filename.lower().endswith(".css") or file.content_type == "text/css"):
        raise HTTPException(status_code=400, detail="Expected a CSS file")
    data = await file.read()
    path = _tenant_dir(organization.id) / "theme.css"
    path.write_bytes(data)
    body = {"uploaded": True, "path": f"/static/tenants/{organization.id}/theme.css"}
    import json as _json
    return JSONResponse(body, headers={"x-test-json-body": _json.dumps(body)})


@router.get("/current")
def get_current_theme(
    organization = Depends(get_current_organization),
) -> JSONResponse:
    """Return current tenant theme asset URLs (for testing and UI helpers)."""
    css_url = f"/static/tenants/{organization.id}/theme.css"
    logo_url = f"/static/tenants/{organization.id}/logo.png"
    import os
    css_exists = os.path.exists(os.path.join(settings.frontend_static_dir, "tenants", str(organization.id), "theme.css"))
    logo_exists = os.path.exists(os.path.join(settings.frontend_static_dir, "tenants", str(organization.id), "logo.png"))
    data = {"tenant_css": css_url if css_exists else None, "tenant_logo": logo_url if logo_exists else None}
    import json as _json
    return JSONResponse(data, headers={"x-test-json-body": _json.dumps(data)})
