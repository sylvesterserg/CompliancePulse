from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..models import ApiKey
from ..schemas import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyView
from ..security.api_keys import ApiKeyManager
from ..security.rate_limit import rate_limit
from .deps import get_db_session

router = APIRouter(prefix="/settings/api-keys", tags=["api-keys"])


@router.get("", response_model=List[ApiKeyView], dependencies=[Depends(rate_limit("api-keys:list", 30, 60))])
def list_api_keys(session: Session = Depends(get_db_session)) -> List[ApiKeyView]:
    manager = ApiKeyManager(session)
    return manager.list_keys()


@router.post(
    "/create",
    response_model=ApiKeyCreateResponse,
    dependencies=[Depends(rate_limit("api-keys:create", 5, 3600))],
)
def create_api_key(payload: ApiKeyCreateRequest, session: Session = Depends(get_db_session)) -> ApiKeyCreateResponse:
    manager = ApiKeyManager(session)
    key, record = manager.create_key(
        organization_id=payload.organization_id,
        name=payload.name,
        scopes=payload.scopes,
    )
    return ApiKeyCreateResponse.from_pair(key, record)


@router.post(
    "/{api_key_id}/revoke",
    response_model=ApiKeyView,
    dependencies=[Depends(rate_limit("api-keys:revoke", 10, 3600))],
)
def revoke_api_key(api_key_id: int, session: Session = Depends(get_db_session)) -> ApiKeyView:
    manager = ApiKeyManager(session)
    key = manager.revoke_key(api_key_id)
    return ApiKeyView.from_orm(key)


@router.get(
    "/{api_key_id}/show",
    response_model=ApiKeyView,
    dependencies=[Depends(rate_limit("api-keys:show", 60, 60))],
)
def show_api_key(api_key_id: int, session: Session = Depends(get_db_session)) -> ApiKeyView:
    api_key = session.get(ApiKey, api_key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return ApiKeyView.from_orm(api_key)
