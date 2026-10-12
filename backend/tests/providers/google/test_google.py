import httpx
import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.providers.google.places import GoogleProvider


async def test_google_wire_format_and_unknown_octane():
    def handler(request):
        assert request.headers["X-Goog-Api-Key"] == "fixture"
        assert "fuelOptions" in request.headers["X-Goog-FieldMask"]
        assert "places.currentOpeningHours.openNow" in request.headers["X-Goog-FieldMask"]
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "abc",
                        "displayName": {"text": "Shell"},
                        "addressComponents": [{"types": ["country"], "shortText": "US"}],
                        "location": {"latitude": 34, "longitude": -118},
                        "businessStatus": "OPERATIONAL",
                        "currentOpeningHours": {"openNow": False},
                        "fuelOptions": {
                            "fuelPrices": [
                                {
                                    "type": "PREMIUM",
                                    "price": {"currencyCode": "USD", "units": "5", "nanos": 999000000},
                                    "updateTime": "2026-10-09T15:30:00Z",
                                }
                            ]
                        },
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        stations = await GoogleProvider(client, "fixture").stations(Search(origin=Point(lat=34, lng=-118)))
    assert str(stations[0].price_per_gallon) == "5.999"
    assert stations[0].octane is None
    assert stations[0].price_updated_at.tzinfo is not None
    assert stations[0].open_now is False and stations[0].business_status == "operational"


async def test_route_sends_stopover_and_reads_duration():
    import json

    def handler(request):
        assert len(json.loads(request.content)["intermediates"]) == 1
        return httpx.Response(200, json={"routes": [{"distanceMeters": 1600, "duration": "120.5s"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        route = await GoogleProvider(client, "fixture").route(
            Point(lat=34, lng=-118), Point(lat=35, lng=-118), Point(lat=34.5, lng=-118)
        )
    assert route.duration_seconds == 120.5


async def test_upstream_error_is_sanitized():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(403, text="secret"))
    ) as client:
        with pytest.raises(ProviderError, match="upstream_rejected_request"):
            await GoogleProvider(client, "fixture").stations(Search(origin=Point(lat=0, lng=0)))


async def test_cross_provider_join_requires_exact_station_address():
    import json
    from datetime import UTC, datetime

    from gaswise.contracts.sources import GasBuddyQuote

    quote = GasBuddyQuote(
        id="gb1",
        name="Chevron",
        address="1516 S Main St, Los Angeles, CA 90015",
        street="1516 S Main St",
        city="Los Angeles",
        region="CA",
        postal_code="90015",
        price_per_gallon="6.95",
        fuel_type="premium",
        payment_type="credit",
        price_updated_at=None,
        fetched_at=datetime.now(UTC),
        report_kind="datafeed",
        source_url="https://www.gasbuddy.com/station/gb1",
    )
    components = [
        {"types": ["country"], "shortText": "US"},
        {"types": ["street_number"], "longText": "1516"},
        {"types": ["route"], "shortText": "S Main St"},
        {"types": ["locality"], "longText": "Los Angeles"},
        {"types": ["administrative_area_level_1"], "shortText": "CA"},
        {"types": ["postal_code"], "longText": "90015"},
    ]

    def handler(request):
        assert json.loads(request.content)["strictTypeFiltering"] is True
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "google1",
                        "location": {"latitude": 34, "longitude": -118},
                        "addressComponents": components,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GoogleProvider(client, "fixture")
        located = await provider.locate_station(quote)
        assert located[0] == "google1"
        assert await provider.locate_station(quote.model_copy(update={"street": "1518 S Main St"})) is None


async def test_google_price_endpoint_only_calls_nearby(monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from gaswise.app.settings import Settings
    from gaswise.main import create_app

    calls = []
    original_client = httpx.AsyncClient

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://places.googleapis.com/v1/places:searchNearby"
        assert json.loads(request.content)["maxResultCount"] == 20
        return httpx.Response(200, json={"places": []})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    settings = Settings(
        mode="prices_only", gasbuddy_web_enabled=True, google_api_key="fixture", api_token="local"
    )
    with TestClient(create_app(settings)) as client:
        body = {"origin": {"lat": 34.05, "lng": -118.25}}
        assert client.post("/v1/sources/google/prices", json=body).status_code == 401
        response = client.post(
            "/v1/sources/google/prices", json=body, headers={"Authorization": "Bearer local"}
        )
        assert response.status_code == 200
        assert response.json()["stations"] == []
        assert response.headers["cache-control"] == "no-store"
        assert len(calls) == 1
        body["max_results"] = 21
        assert (
            client.post(
                "/v1/sources/google/prices", json=body, headers={"Authorization": "Bearer local"}
            ).status_code
            == 422
        )
        assert len(calls) == 1


def test_google_price_endpoint_missing_key():
    from fastapi.testclient import TestClient

    from gaswise.app.settings import Settings
    from gaswise.main import create_app

    with TestClient(create_app(Settings(mode="demo"))) as client:
        response = client.post("/v1/sources/google/prices", json={"origin": {"lat": 34, "lng": -118}})
    assert response.status_code == 503
    assert response.json()["detail"] == "google_places_not_configured"


@pytest.mark.parametrize(
    "status,code", [(429, "google_quota_or_rate_limit_exceeded"), (503, "upstream_unavailable")]
)
async def test_google_failures_do_not_retry(status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private upstream error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match=code):
            await GoogleProvider(client, "fixture").stations(Search(origin=Point(lat=34, lng=-118)))
    assert len(calls) == 1


def test_google_opening_status_is_unknown_without_hours():
    assert GoogleProvider.opening({}) == {"open_now": None, "business_status": None}
    assert GoogleProvider.opening({"businessStatus": "CLOSED_TEMPORARILY"})["business_status"] == (
        "temporarily_closed"
    )
