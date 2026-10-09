from datetime import UTC, datetime

import httpx
import pytest

from gaswise.models import Point, Search, Station
from gaswise.providers.base import ProviderError
from gaswise.providers.gasbuddy import GasBuddyFeedProvider
from gaswise.settings import Settings


async def test_contracted_feed_normalizes_provenance_and_exact_crosswalk():
    quote = Station(
        id="gb1",
        canonical_id="google_places:place1",
        name="Shell",
        location=Point(lat=34, lng=-118),
        price_per_gallon="6",
        fuel_type="premium",
        payment_type="credit",
        fetched_at=datetime.now(UTC),
        source="gasbuddy",
    )

    def handler(request):
        assert request.headers["Authorization"] == "Bearer fixture"
        return httpx.Response(
            200,
            json={"schema_version": "gaswise.gasbuddy-feed.v1", "stations": [quote.model_dump(mode="json")]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await GasBuddyFeedProvider(client, "https://feed.example/prices", "fixture").stations(
            Search(origin=Point(lat=34, lng=-118))
        )
    assert records[0].canonical_id == "google_places:place1"


async def test_missing_schema_version_is_rejected():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"stations": []}))
    ) as client:
        with pytest.raises(ProviderError, match="gasbuddy_feed_invalid_response"):
            await GasBuddyFeedProvider(client, "https://feed.example/prices", "fixture").stations(
                Search(origin=Point(lat=34, lng=-118))
            )


def test_feed_requires_https_and_token():
    with pytest.raises(ValueError):
        Settings(
            api_token="local", gasbuddy_feed_url="http://feed.example/prices", gasbuddy_feed_token="fixture"
        )
    with pytest.raises(ValueError):
        Settings(api_token="local", gasbuddy_feed_url="https://feed.example/prices")
