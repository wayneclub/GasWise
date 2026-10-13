import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.providers.gasbuddy.http_session import GRAPHQL, LANDING, GasBuddyHTTPSession
from gaswise.providers.gasbuddy.web import GasBuddyWebProvider

QUERY = Search(origin=Point(lat=34.04, lng=-118.27), postal_code="90015")


def fixture_worker(challenge=False, api_rejected=False):
    calls = {"bootstrap": 0, "api": 0, "clients": []}

    def handler(request):
        if request.method == "GET":
            assert str(request.url) == LANDING, "Never fetch the challenged /home path"
            calls["bootstrap"] += 1
            if challenge:
                return httpx.Response(403, headers={"cf-mitigated": "challenge"}, text="challenge")
            return httpx.Response(
                200,
                headers={"set-cookie": "guest_session=fixture; Path=/; Secure"},
                text='<script>window.gbcsrf = "fixture-csrf";</script>',
            )
        assert str(request.url) == GRAPHQL
        assert request.headers["gbcsrf"] == "fixture-csrf"
        assert request.headers["Referer"] == LANDING
        assert "guest_session=fixture" in request.headers["Cookie"]
        assert "Authorization" not in request.headers
        calls["api"] += 1
        if api_rejected:
            return httpx.Response(403, text="denied")
        price = 5.99 + calls["api"] / 100
        return httpx.Response(
            200,
            json={
                "data": {
                    "locationBySearchTerm": {
                        "stations": {
                            "cursor": {"next": None},
                            "results": [
                                {
                                    "id": "1",
                                    "name": "Example",
                                    "priceUnit": "dollars_per_gallon",
                                    "address": {
                                        "country": "US",
                                        "line1": "1 Main St",
                                        "locality": "Los Angeles",
                                        "region": "CA",
                                        "postalCode": "90015",
                                    },
                                    "prices": [
                                        {
                                            "fuelProduct": "premium_gas",
                                            "credit": {
                                                "price": price,
                                                "postedTime": datetime.now(UTC).isoformat(),
                                                "nickname": "DataFeed",
                                            },
                                            "cash": {"price": 5},
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                }
            },
        )

    def factory():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        calls["clients"].append(client)
        return client

    return GasBuddyHTTPSession(client_factory=factory, session_seconds=60), calls


async def test_clean_http_bootstrap_and_fresh_quote_each_request():
    worker, calls = fixture_worker()
    async with httpx.AsyncClient() as client:
        provider = GasBuddyWebProvider(client, snapshot_loader=worker.snapshot, transport="http")
        first = await provider.prices(QUERY)
        second = await provider.prices(QUERY)
    assert first.transport == "http" and second.transport == "http"
    assert first.prices[0].name == "Example"
    assert first.prices[0].payment_type == "credit"
    assert first.prices[0].price_per_gallon != second.prices[0].price_per_gallon
    assert calls["bootstrap"] == 1 and calls["api"] == 2
    await worker.close()
    assert calls["clients"][0].is_closed and worker._csrf is None


async def test_global_anonymous_session_can_query_new_zip_without_new_bootstrap():
    worker, calls = fixture_worker()
    await worker.snapshot(QUERY, "unused", 3)
    await worker.snapshot(QUERY.model_copy(update={"postal_code": "90016"}), "unused", 3)
    assert calls["bootstrap"] == 1 and calls["api"] == 2
    await worker.close()


async def test_age_expiry_creates_new_cookie_jar():
    worker, calls = fixture_worker()
    await worker.snapshot(QUERY, "unused", 3)
    worker._created_at -= 61
    await worker.snapshot(QUERY, "unused", 3)
    assert calls["bootstrap"] == 2
    assert calls["clients"][0].is_closed
    assert not calls["clients"][1].is_closed
    await worker.close()


async def test_idle_expiry_removes_cookie_jar_without_next_query():
    worker, calls = fixture_worker()
    worker.session_seconds = 0.01
    await worker.snapshot(QUERY, "unused", 3)
    await asyncio.sleep(0.02)
    assert worker._client is None and worker._csrf is None
    assert calls["clients"][0].is_closed


@pytest.mark.parametrize(
    "kwargs,expected",
    [({"challenge": True}, "bootstrap_challenge"), ({"api_rejected": True}, "api_rejected")],
)
async def test_denied_session_is_not_retried_or_switched_to_browser(kwargs, expected):
    worker, calls = fixture_worker(**kwargs)
    with pytest.raises(ProviderError, match=expected):
        await worker.snapshot(QUERY, "unused", 3)
    assert calls["bootstrap"] == 1
    assert calls["api"] <= 1
    assert calls["clients"][0].is_closed and worker._csrf is None


async def test_cursor_pages_recover_later_station_with_its_own_metadata():
    import json

    from gaswise.contracts.sources import GasBuddySearch

    cursors = []
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, text='<script>window.gbcsrf = "fixture";</script>')
        cursor = json.loads(request.content)["variables"].get("cursor")
        cursors.append(cursor)
        number = len(cursors)
        return httpx.Response(200, json={"data":{"locationBySearchTerm":{"stations":{
            "cursor":{"next":"next" if number == 1 else None},
            "results":[{"id":str(number),"name":"Later station" if number == 2 else "First station","priceUnit":"dollars_per_gallon","address":{"country":"US","line1":f"{number} Main St","locality":"Los Angeles","region":"CA","postalCode":"90021"},"prices":[{"fuelProduct":"premium_gas","credit":{"price":6.37,"postedTime":datetime.now(UTC).isoformat()}}]}]
        }}}})
    worker = GasBuddyHTTPSession(client_factory=lambda:httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    provider = GasBuddyWebProvider(None, snapshot_loader=worker.snapshot, transport="http")
    try:
        result = await provider.prices(GasBuddySearch(postal_code="90021", max_pages=3, max_results=100))
        assert cursors == [None, "next"]
        assert result.page_requests == 2 and result.partial is False
        assert {q.name for q in result.prices} == {"First station", "Later station"}
    finally:
        await worker.close()


async def test_default_client_routes_only_through_configured_proxy():
    worker = GasBuddyHTTPSession(proxy="http://gluetun:8888")
    client = worker._factory()
    try:
        assert client._trust_env is False
        [(pattern, transport)] = client._mounts.items()
        assert pattern.pattern == "all://"
        assert transport._pool._proxy_url.host == b"gluetun"
    finally:
        await client.aclose()
