import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from gaswise.api.dependencies import get_services, get_settings
from gaswise.api.history import router
from gaswise.app.settings import Settings
from gaswise.providers.storage.postgres import PostgresPricingCache


@pytest.mark.asyncio
async def test_observations_preserve_unknown_report_time_and_conditions():
    now = datetime.now(UTC)
    row = dict(source="waze", station_id="one", payment_type="unknown", purchase_condition="member",
               price_per_gallon=Decimal("4.199"), reported_at=None, first_seen_at=now,
               attributes=json.dumps({"membership_required": "Club", "octane": 91}))
    pool = SimpleNamespace(fetch=AsyncMock(return_value=[row] * 1001))
    result = await PostgresPricingCache(pool).price_history(None, "waze", "one", "premium", 7)
    assert result["truncated"] is True
    assert len(result["observations"]) == 1000
    assert result["observations"][0] == dict(source="waze", station_id="one", payment_type="unknown",
        condition="member", price="4.199", reported_at=None, observed_at=now.isoformat(), membership="Club", octane=91)
    assert pool.fetch.call_args.args[1:] == (None, "waze", "one", "premium", 7)


@pytest.mark.asyncio
async def test_history_endpoint_bounded_input_and_unavailable_storage():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: Settings(api_token="")
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(smart=SimpleNamespace(shared_cache=None))
    body = dict(source="waze", station_id="one", fuel_type="regular", days=30)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/v1/prices/history", json=body)).status_code == 503
        assert (await client.post("/v1/prices/history", json={**body, "days": 365})).status_code == 422
        cache = SimpleNamespace(price_history=AsyncMock(return_value={"observations": [], "truncated": False}))
        app.dependency_overrides[get_services] = lambda: SimpleNamespace(smart=SimpleNamespace(shared_cache=cache))
        response = await client.post("/v1/prices/history", json=body)
        assert response.json() == {"observations": [], "truncated": False}
        cache.price_history.assert_awaited_once_with(None, "waze", "one", "regular", 30)
