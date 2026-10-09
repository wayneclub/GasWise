import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from playwright.async_api import Error as BrowserError
from playwright.async_api import TimeoutError as BrowserTimeout

from gaswise.models import Point, Search
from gaswise.providers.base import ProviderError
from gaswise.providers.browser_worker import GasBuddyBrowserWorker
from gaswise.providers.gasbuddy_web import GasBuddyWebProvider

QUERY = Search(origin=Point(lat=34.04, lng=-118.27), postal_code="90015")
URL = "https://www.gasbuddy.com/home?search=90015&fuel=3&method=credit&maxAge=0"


class ExpectResponse:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        self.value = asyncio.get_running_loop().create_future()
        self.value.set_result(self.response)
        return self

    async def __aexit__(self, *_):
        return False


def worker_fixture(status=200, price_ok=True, fail=None):
    response = SimpleNamespace(
        ok=price_ok,
        json=AsyncMock(return_value={"data": {"locationBySearchTerm": {"stations": {"results": []}}}}),
    )
    page = SimpleNamespace(
        set_default_timeout=lambda _: None,
        goto=AsyncMock(return_value=SimpleNamespace(status=status), side_effect=fail),
        expect_response=lambda predicate, timeout: ExpectResponse(response),
        content=AsyncMock(return_value='<script>window.__APOLLO_STATE__ = {"Station:1":{}};</script>'),
    )
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), is_connected=lambda: True)
    worker = GasBuddyBrowserWorker()
    worker._browser = browser
    worker._ensure_browser = AsyncMock()
    return worker, context


async def test_worker_reads_page_response_and_closes_anonymous_context():
    worker, context = worker_fixture()
    state, listing = await worker.snapshot(QUERY, URL, 3)
    assert state == {"Station:1": {}}
    assert listing == {"results": []}
    context.close.assert_awaited_once()


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"status": 403}, "navigation_rejected"),
        ({"price_ok": False}, "price_request_rejected"),
        ({"fail": BrowserTimeout("timeout")}, "timeout_or_challenge"),
        ({"fail": BrowserError("sensitive browser diagnostics")}, "browser_unavailable"),
    ],
)
async def test_rejection_timeout_and_errors_cleanup_without_fallback(kwargs, error):
    worker, context = worker_fixture(**kwargs)
    with pytest.raises(ProviderError, match=error):
        await worker.snapshot(QUERY, URL, 3)
    context.close.assert_awaited_once()


async def test_cancellation_closes_context():
    worker, context = worker_fixture(fail=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await worker.snapshot(QUERY, URL, 3)
    context.close.assert_awaited_once()


async def test_browser_payload_uses_same_credit_and_provenance_parser():
    async def loader(query, url, fuel):
        assert "method=credit" in url and fuel == 3
        return {
            "Station:1": {
                "name": "Example",
                "priceUnit": "dollars_per_gallon",
                "address": {
                    "country": "US",
                    "line1": "1 Main St",
                    "locality": "Los Angeles",
                    "region": "CA",
                    "postalCode": "90015",
                },
            }
        }, {
            "results": [
                {
                    "id": "1",
                    "prices": [
                        {
                            "fuelProduct": "premium_gas",
                            "cash": {"price": 5},
                            "credit": {
                                "price": 6,
                                "postedTime": "2026-10-09T20:00:00Z",
                                "nickname": "DataFeed",
                            },
                        }
                    ],
                }
            ],
            "cursor": {},
        }

    async with httpx.AsyncClient() as client:
        data = await GasBuddyWebProvider(client, snapshot_loader=loader).prices(QUERY)
    assert data.transport == "browser"
    assert data.prices[0].price_per_gallon == 6
    assert data.prices[0].source == "gasbuddy_web"
    assert data.prices[0].price_updated_at is not None


def test_prices_only_mode_exposes_live_price_source_without_demo_recommendations():
    from fastapi.testclient import TestClient

    from gaswise.main import create_app
    from gaswise.settings import Settings

    settings = Settings(mode="prices_only", gasbuddy_web_enabled=True, api_token="fixture")
    with TestClient(create_app(settings)) as client:
        headers = {"Authorization": "Bearer fixture"}
        capabilities = client.get("/v1/capabilities", headers=headers).json()
        assert capabilities["mode"] == "prices_only"
        assert capabilities["recommendations_enabled"] is False
        assert (
            client.post("/v1/recommendations", json=QUERY.model_dump(mode="json"), headers=headers).json()[
                "detail"
            ]
            == "routing_provider_not_configured"
        )
