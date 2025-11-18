import asyncio
import pytest
from sqlmodel import select

from backend.app.models import Rule


@pytest.mark.integration
def test_rule_listing_and_detail(auth_client, session):
    listing = asyncio.run(auth_client.get("/rules"))
    assert listing.status_code == 200
    # Fetch first rule id from DB to avoid UI fallback ambiguity
    rule = session.exec(select(Rule)).first()
    assert rule is not None
    detail = asyncio.run(auth_client.get(f"/rules/{rule.id}"))
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["id"] == rule.id
    assert payload["benchmark_id"] == rule.benchmark_id


@pytest.mark.integration
def test_reports_listing(auth_client):
    listing = asyncio.run(auth_client.get("/reports"))
    assert listing.status_code == 200
