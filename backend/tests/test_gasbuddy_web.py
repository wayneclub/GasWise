import json
from datetime import UTC, datetime

import httpx
import pytest

from gaswise.models import Point, Search
from gaswise.providers.base import ProviderError
from gaswise.providers.gasbuddy_web import GasBuddyWebProvider

ORIGIN = Point(lat=34.03938, lng=-118.2663)


def transport(price=6.95, credit=True, timestamp=None, blocked=False):
    metadata = {
        "Station:11034": {
            "name": "Chevron",
            "priceUnit": "dollars_per_gallon",
            "address": {
                "country": "US",
                "line1": "1516 S Main St",
                "locality": "Los Angeles",
                "region": "CA",
                "postalCode": "90015-2504",
            },
        }
    }
    html = (
        "<script>window.__APOLLO_STATE__ = "
        + json.dumps(metadata)
        + '; window.gbcsrf = "fixture-session-token";</script>'
    )

    def handler(request):
        if request.method == "GET":
            assert "search=90015" in str(request.url)
            return httpx.Response(200, text=html)
        assert request.url.path == "/graphql"
        assert request.headers["gbcsrf"] == "fixture-session-token"
        payload = json.loads(request.content)
        assert payload["variables"]["fuel"] == 3
        assert payload["variables"]["maxAge"] == 0
        if blocked:
            return httpx.Response(403, text="blocked")
        return httpx.Response(
            200,
            json={
                "data": {
                    "locationBySearchTerm": {
                        "stations": {
                            "count": 1,
                            "cursor": {"next": None},
                            "results": [
                                {
                                    "id": "11034",
                                    "prices": [
                                        {
                                            "fuelProduct": "premium_gas",
                                            "cash": {
                                                "price": 6.79,
                                                "postedTime": timestamp,
                                                "nickname": "DataFeed",
                                            },
                                            "credit": {
                                                "price": price,
                                                "postedTime": timestamp,
                                                "nickname": "DataFeed",
                                            }
                                            if credit
                                            else None,
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                }
            },
        )

    return httpx.MockTransport(handler)


async def test_reads_credit_price_not_cheaper_cash_and_preserves_timestamp():
    timestamp = datetime.now(UTC).isoformat()
    async with httpx.AsyncClient(transport=transport(timestamp=timestamp)) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert str(result.prices[0].price_per_gallon) == "6.95"
    assert result.prices[0].payment_type == "credit"
    assert result.prices[0].price_updated_at.isoformat() == timestamp
    assert result.prices[0].octane is None
    assert result.prices[0].report_kind == "datafeed"


async def test_no_credit_never_falls_back_to_cash():
    async with httpx.AsyncClient(transport=transport(credit=False)) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert result.prices == []


async def test_zero_missing_price_is_not_a_free_station():
    async with httpx.AsyncClient(transport=transport(price=0)) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert result.prices == []


async def test_unknown_source_time_stays_unknown_after_fetch():
    async with httpx.AsyncClient(transport=transport()) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert result.prices[0].price_updated_at is None


async def test_block_is_explicit_and_does_not_fabricate_data():
    async with httpx.AsyncClient(transport=transport(blocked=True)) as client:
        with pytest.raises(ProviderError, match="gasbuddy_web_access_rejected"):
            await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))


async def test_schema_change_is_not_empty_success():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="changed"))
    ) as client:
        with pytest.raises(ProviderError, match="gasbuddy_web_schema_changed"):
            await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))


async def test_postal_code_is_required_for_website_search():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderError, match="gasbuddy_postal_code_required"):
            await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN))
