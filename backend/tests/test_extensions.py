import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.main import create_app
from gaswise.models import Point, Search
from gaswise.providers.feed import HTTPPriceSource
from gaswise.providers.registry import SourceRegistry
from gaswise.settings import Settings

QUERY = Search(origin=Point(lat=34, lng=-118))


class EmptySource:
    async def stations(self, query):
        return []


class BrokenSource:
    async def stations(self, query):
        raise RuntimeError("secret exception text")


class SlowSource:
    async def stations(self, query):
        await asyncio.sleep(1)
        return []


async def test_timeout_and_unexpected_error_are_isolated():
    registry = SourceRegistry()
    registry.register("ok", EmptySource())
    registry.register("slow", SlowSource(), 0.01)
    registry.register("broken", BrokenSource())
    snapshot = await registry.provider().snapshot(QUERY)
    statuses = {s.source: s for s in snapshot.statuses}
    assert statuses["ok"].status == "ok"
    assert statuses["slow"].detail == "source_timeout"
    assert statuses["broken"].detail == "source_internal_error"
    with pytest.raises(ValueError, match="duplicate"):
        registry.register("ok", EmptySource())


async def test_http_feed_contract_and_auth():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer private-token"
        assert request.method == "POST"
        return httpx.Response(200, json={"schema_version": "gaswise.price-feed.v1", "stations": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = HTTPPriceSource(client, "partner", "https://example.com/prices", "private-token")
        assert await source.stations(QUERY) == []


def test_configured_feed_discovery_does_not_expose_credentials():
    settings = Settings(
        mode="prices_only",
        gasbuddy_web_enabled=False,
        api_token="test",
        price_sources=[{"source_id": "partner", "url": "https://example.com/prices", "token": "secret"}],
    )
    with TestClient(create_app(settings)) as client:
        r = client.get("/v1/sources", headers={"Authorization": "Bearer test"})
    assert r.status_code == 200
    assert "secret" not in r.text and "example.com" not in r.text
    assert r.json()["sources"][0]["source"] == "partner"


@pytest.mark.parametrize(
    "sources",
    [
        [{"source_id": "gasbuddy_web", "url": "https://example.com"}],
        [{"source_id": "a", "url": "http://example.com"}],
        [{"source_id": "a", "url": "https://example.com"}, {"source_id": "a", "url": "https://example.com"}],
    ],
)
def test_invalid_source_configuration_rejected(sources):
    with pytest.raises(ValueError):
        Settings(mode="prices_only", api_token="test", price_sources=sources)
