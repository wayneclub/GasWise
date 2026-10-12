import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gaswise.app.settings import Settings
from gaswise.contracts.vehicles import PlateRequest
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.providers.vehicles.plate import PlateProvider
from gaswise.providers.vehicles.vin import VinProvider
from gaswise.services.vehicles.plate_selection import PlateSelector
from gaswise.services.vehicles.vin_selection import VinSelector
from tests.support.plate import (
    PLATE as PLATE,
)
from tests.support.plate import (
    RESPONSE as RESPONSE,
)
from tests.support.service import FixtureProvider
from tests.support.vin import VIN, catalog, decoder


def test_normalization_and_state_required():
    query = PlateRequest(plate="test-123", state="ca")
    assert query.plate == PLATE
    assert query.state == "CA"
    with pytest.raises(ValidationError):
        PlateRequest(plate=PLATE)


@pytest.mark.parametrize(
    "values",
    [
        {"plate": "../secret", "state": "CA"},
        {"plate": "---", "state": "CA"},
        {"plate": "TEST", "state": "ZZ"},
        {"plate": "TEST", "state": "ON"},
        {"plate": "車牌", "state": "CA"},
    ],
)
def test_invalid_plate_or_state_rejected(values):
    with pytest.raises(ValidationError):
        PlateRequest(**values)


async def test_documented_endpoint_and_secret_header():
    def handler(request):
        assert str(request.url) == "https://api.vehicledatabases.com/plate-decode/TEST123/CA"
        assert request.headers["x-authkey"] == "fixture-key"
        assert "fixture-key" not in str(request.url)
        return httpx.Response(200, json=RESPONSE)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        vin, make, model = await PlateProvider(client, "fixture-key").vin(
            PlateRequest(plate=PLATE, state="CA")
        )
    assert vin.vin == VIN
    assert vin.model_year == 2011
    assert (make, model) == ("BMW", "X3")


@pytest.mark.parametrize(
    "changes",
    [
        {"license": "OTHER123"},
        {"state": "NY"},
        {"vin": "bad"},
    ],
)
async def test_identity_mismatch_or_invalid_vin_rejected(changes):
    response = {
        "status": "success",
        "data": {"intro": {**RESPONSE["data"]["intro"], **changes}, "basic": RESPONSE["data"]["basic"]},
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))
    ) as client:
        with pytest.raises(ProviderError, match="plate_invalid_response"):
            await PlateProvider(client, "fixture-key").vin(PlateRequest(plate=PLATE, state="CA"))


@pytest.mark.parametrize(
    "status,message",
    [
        (400, "plate_record_not_found"),
        (401, "plate_provider_authentication_failed"),
        (429, "plate_provider_rate_limited"),
        (500, "plate_provider_unavailable"),
    ],
)
async def test_failure_does_not_retry(status, message):
    calls = []

    def fail(request):
        calls.append(request)
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(ProviderError, match=message):
            await PlateProvider(client, "fixture-key").vin(PlateRequest(plate=PLATE, state="CA"))
    assert len(calls) == 1


async def test_plate_to_vin_to_epa_full_synthetic_flow():
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=RESPONSE))
        ) as plates,
        decoder() as vins,
        httpx.AsyncClient(transport=httpx.MockTransport(catalog)) as epa,
    ):
        result = await PlateSelector(
            PlateProvider(plates, "fixture-key"), VinSelector(VinProvider(vins), VehicleProvider(epa))
        ).resolve(PlateRequest(plate=PLATE, state="CA"))
    assert result.resolution.status == "resolved"
    assert result.resolution.vehicle.id == 123
    assert result.resolution.fuel_recommendation.fuel_type == "premium"
    assert result.resolution.upstream_calls["plate_lookup"] == 1
    assert PLATE not in result.model_dump_json()
    assert VIN not in result.model_dump_json()


async def test_plate_and_vin_make_mismatch_stops_before_epa():
    response = {
        "status": "success",
        "data": {**RESPONSE["data"], "basic": {**RESPONSE["data"]["basic"], "make": "Honda"}},
    }
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))
        ) as plates,
        decoder() as vins,
    ):
        with pytest.raises(ProviderError, match="plate_vin_vehicle_mismatch"):
            await PlateSelector(
                PlateProvider(plates, "fixture-key"), VinSelector(VinProvider(vins), None)
            ).resolve(PlateRequest(plate=PLATE, state="CA"))


async def test_model_label_disagreement_requires_confirmation_without_epa():
    response = {
        "status": "success",
        "data": {**RESPONSE["data"], "basic": {**RESPONSE["data"]["basic"], "model": "X5"}},
    }
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))
        ) as plates,
        decoder() as vins,
    ):
        result = await PlateSelector(
            PlateProvider(plates, "fixture-key"), VinSelector(VinProvider(vins), None)
        ).resolve(PlateRequest(plate=PLATE, state="CA"))
    assert result.resolution.status == "needs_input"
    assert result.resolution.vehicle is None
    assert result.resolution.upstream_calls["epa_lookup"] == 0


def test_disabled_endpoint_and_capabilities_make_no_calls(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("disabled provider must make zero network calls")

    monkeypatch.setattr(httpx.AsyncClient, "get", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    with TestClient(create_app(Settings(_env_file=None), FixtureProvider())) as client:
        assert client.get("/v1/capabilities").json()["plate_lookup_enabled"] is False
        response = client.post("/v1/vehicles/plate", json={"plate": PLATE, "state": "CA"})
    assert response.status_code == 503
    assert response.json()["detail"] == "plate_provider_not_configured"


def test_enabled_provider_requires_both_keys():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, plate_lookup_enabled=True, vehicle_databases_api_key="fixture-key", api_token=""
        )


def test_http_plate_endpoint_with_synthetic_providers():
    with TestClient(
        create_app(
            Settings(_env_file=None),
            FixtureProvider(),
            vehicle_provider=VehicleProvider(httpx.AsyncClient(transport=httpx.MockTransport(catalog))),
            vin_provider=VinProvider(decoder()),
            plate_provider=PlateProvider(
                httpx.AsyncClient(
                    transport=httpx.MockTransport(lambda r: httpx.Response(200, json=RESPONSE))
                ),
                "fixture-key",
            ),
        )
    ) as client:
        result = client.post("/v1/vehicles/plate", json={"plate": PLATE, "state": "CA"})
        assert result.status_code == 200
        assert result.json()["resolution"]["status"] == "resolved"
        assert PLATE not in result.text
