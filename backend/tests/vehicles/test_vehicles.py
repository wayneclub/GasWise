from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.contracts.search import RankOptions, Search
from gaswise.contracts.smart import SmartRerank, SmartSearch
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.services.pricing.search import SearchService
from gaswise.services.pricing.smart import SmartService
from tests.support.service import FixtureProvider
from tests.support.smart import CountingProvider
from tests.support.vehicles import (
    RECORD as RECORD,
)


async def test_record_identity_units_and_bounded_cache():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=RECORD)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = VehicleProvider(client)
        vehicle = await provider.vehicle(123)
        again = await provider.vehicle(123)
        assert len(calls) == 1
        assert again == vehicle
        assert vehicle.combined_mpg == Decimal(30)
        assert vehicle.powertrain == "gasoline"
        assert vehicle.source == "fueleconomy_gov"
        again.combined_mpg = Decimal(1)
        assert (await provider.vehicle(123)).combined_mpg == Decimal(30)
        for i in range(130):
            provider.remember((str(i), ()), vehicle)
        assert len(provider.cache) == 128


@pytest.mark.parametrize(
    "changes",
    [
        {"fuelType1": "Electricity", "atvType": "EV"},
        {"fuelType2": "Electricity", "atvType": "Plug-in Hybrid"},
        {"fuelType2": "E85", "atvType": "FFV"},
        {"fuelType1": "Hydrogen"},
    ],
)
async def test_unsupported_powertrain_never_returns_mpg(changes):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={**RECORD, **changes}))
    ) as client:
        with pytest.raises(ProviderError, match="vehicle_powertrain_not_supported"):
            await VehicleProvider(client).vehicle(123)


@pytest.mark.parametrize("changes", [{"id": "124"}, {"comb08": "0"}, {"city08": "NaN"}])
async def test_invalid_or_wrong_vehicle_is_not_cached(changes):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={**RECORD, **changes}))
    ) as client:
        provider = VehicleProvider(client)
        with pytest.raises(ProviderError, match="vehicle_catalog_invalid_vehicle"):
            await provider.vehicle(123)
        assert not provider.cache


async def test_single_menu_item_and_query_encoding():
    def handler(request):
        assert request.url.params["make"] == "A&B"
        return httpx.Response(200, json={"menuItem": {"text": "Car", "value": "123"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleProvider(client).menu("model", year=2020, make="A&B")
    assert result.items[0].value == "123"


async def test_lookup_failure_stops_before_price_and_route_calls():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        provider = CountingProvider()
        with pytest.raises(ProviderError, match="vehicle_catalog_unavailable"):
            await SearchService(provider, "demo", vehicles=VehicleProvider(client)).search(
                Search(origin=Point(lat=34, lng=-118), vehicle_id=123, fuel_type="premium")
            )
        assert (provider.searches, provider.routes) == (0, 0)


async def test_diesel_fuel_mismatch_stops_before_price_calls():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={**RECORD, "fuelType1": "Diesel", "atvType": "Diesel"})
        )
    ) as client:
        provider = CountingProvider()
        with pytest.raises(ProviderError, match="vehicle_fuel_type_mismatch"):
            await SearchService(provider, "demo", vehicles=VehicleProvider(client)).search(
                Search(origin=Point(lat=34, lng=-118), vehicle_id=123, fuel_type="premium")
            )
        assert (provider.searches, provider.routes) == (0, 0)


async def test_signed_vehicle_snapshot_reranks_without_any_new_calls():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=RECORD)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CountingProvider()
        service = SmartService(b"test", "demo", demo=provider, vehicles=VehicleProvider(client))
        first = await service.search(
            SmartSearch(origin=Point(lat=34, lng=-118), vehicle_id=123, calculate_routes=True)
        )
        assert first.ranking.results[0].mpg_used == 30
        assert first.ranking.results[0].fuel_consumption_basis == "epa_combined_estimate"
        assert first.upstream_calls["vehicle_catalog_lookup"] == 1
        counts = provider.searches, provider.routes
        override = await service.rerank(
            SmartRerank(snapshot=first.snapshot, signature=first.signature, options=RankOptions(mpg=10))
        )
        assert override.ranking.results[0].station.name == "Chevron"
        reset = await service.rerank(
            SmartRerank(
                snapshot=override.snapshot, signature=override.signature, options=RankOptions(mpg=None)
            )
        )
        assert reset.ranking.results[0].mpg_used == 30
        assert reset.ranking.vehicle.id == 123
        assert len(calls) == 1
        assert (provider.searches, provider.routes) == counts
        assert not any(reset.upstream_calls.values())
        bad = first.snapshot.model_copy(deep=True)
        bad.vehicle.combined_mpg = Decimal(100)
        with pytest.raises(ProviderError, match="invalid_snapshot_signature"):
            await service.rerank(SmartRerank(snapshot=bad, signature=first.signature, options=RankOptions()))


def test_catalog_endpoints_and_recommendations_auto_mpg():
    def handler(request):
        if "/menu/" in request.url.path:
            return httpx.Response(200, json={"menuItem": [{"text": "Option", "value": "123"}]})
        return httpx.Response(200, json=RECORD)

    with TestClient(
        create_app(
            Settings(),
            FixtureProvider(),
            vehicle_provider=VehicleProvider(httpx.AsyncClient(transport=httpx.MockTransport(handler))),
        )
    ) as client:
        assert client.get("/v1/vehicles/years").status_code == 200
        assert client.get("/v1/vehicles/makes", params={"year": 2020}).status_code == 200
        assert client.get("/v1/vehicles/models", params={"year": 2020, "make": "Fixture"}).status_code == 200
        assert (
            client.get(
                "/v1/vehicles/options", params={"year": 2020, "make": "Fixture", "model": "Car"}
            ).status_code
            == 200
        )
        assert client.get("/v1/vehicles/123").json()["combined_mpg"] == "30"
        response = client.post(
            "/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}, "vehicle_id": 123}
        )
        assert response.status_code == 200
        assert response.json()["results"][0]["mpg_used"] == "30"
        assert client.get("/v1/vehicles/0").status_code == 422
