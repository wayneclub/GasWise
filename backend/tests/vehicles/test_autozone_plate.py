import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gaswise.app.settings import Settings
from gaswise.contracts.vehicles import PlateRequest
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.providers.vehicles.plate import AutoZonePlateProvider
from gaswise.providers.vehicles.vin import VinProvider
from tests.support.plate import PLATE
from tests.support.service import FixtureProvider
from tests.support.vin import VIN, catalog, decoder

RESPONSE = [{"vin": VIN, "makeName": "BMW", "modelName": "X3", "acesVehicleAttributes": {"year": "2011"}}]


async def test_anonymous_contract_strips_inherited_credentials():
    def handle(request):
        assert request.url.host == "external-api.autozone.com"
        assert dict(request.url.params) == {
            "licensePlate": PLATE,
            "state": "CA",
            "callingClient": "DIY-DESKTOP",
            "country": "USA",
        }
        assert request.headers["sales-channel"] == "AZRMFWEB"
        assert not any(k in request.headers for k in ("cookie", "authorization", "x-api-key", "x-authkey"))
        return httpx.Response(200, json=RESPONSE)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        cookies={"session": "private"},
        auth=("private", "private"),
        headers={"x-api-key": "private"},
    ) as client:
        vin, make, model = await AutoZonePlateProvider(client).vin(PlateRequest(plate=PLATE, state="CA"))
    assert (vin.vin, vin.model_year, make, model) == (VIN, 2011, "BMW", "X3")


@pytest.mark.parametrize(
    "status,data,error",
    [
        (404, None, "plate_record_not_found"),
        (401, None, "plate_provider_authentication_failed"),
        (403, None, "plate_provider_authentication_failed"),
        (429, None, "plate_provider_rate_limited"),
        (500, None, "plate_provider_unavailable"),
        (200, [], "plate_record_not_found"),
        (200, RESPONSE * 2, "plate_invalid_response"),
        (200, [{}], "plate_invalid_response"),
        (200, [{**RESPONSE[0], "vin": "bad"}], "plate_invalid_response"),
        (200, {"error": "bad"}, "plate_invalid_response"),
    ],
)
async def test_failures_are_safe_and_do_not_retry(status, data, error):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match=error):
            await AutoZonePlateProvider(client).vin(PlateRequest(plate=PLATE, state="CA"))
    assert len(calls) == 1


def test_settings_require_local_token_but_no_upstream_key():
    Settings(_env_file=None, plate_lookup_enabled=True, plate_lookup_source="autozone", api_token="test")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, plate_lookup_enabled=True, plate_lookup_source="autozone", api_token="")


def test_configured_api_source_wiring_and_masked_response(monkeypatch):
    original = httpx.AsyncClient.send

    async def send(self, request, **kwargs):
        if request.url.host == "external-api.autozone.com":
            return httpx.Response(200, json=RESPONSE, request=request)
        return await original(self, request, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    settings = Settings(
        _env_file=None, plate_lookup_enabled=True, plate_lookup_source="autozone", api_token="test"
    )
    with TestClient(
        create_app(
            settings,
            FixtureProvider(),
            vehicle_provider=VehicleProvider(httpx.AsyncClient(transport=httpx.MockTransport(catalog))),
            vin_provider=VinProvider(decoder()),
        )
    ) as client:
        assert (
            client.get("/v1/capabilities", headers={"Authorization": "Bearer test"}).json()[
                "plate_lookup_source"
            ]
            == "autozone"
        )
        assert client.post("/v1/vehicles/plate", json={"plate": PLATE, "state": "CA"}).status_code == 401
        r = client.post(
            "/v1/vehicles/plate",
            json={"plate": PLATE, "state": "CA"},
            headers={"Authorization": "Bearer test"},
        )
        assert r.status_code == 200
        assert r.json()["resolution"]["status"] == "resolved"
        assert r.json()["source"] == "autozone"
        assert r.json()["source_model"] == "X3"
        assert VIN not in r.text and PLATE not in r.text
