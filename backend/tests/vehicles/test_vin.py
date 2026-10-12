from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gaswise.app.settings import Settings
from gaswise.contracts.vehicles import VinRequest
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.providers.vehicles.vin import VinProvider, check_digit
from gaswise.services.vehicles.vin_selection import VinSelector
from tests.support.service import FixtureProvider
from tests.support.vehicles import RECORD
from tests.support.vin import (
    DECODE as DECODE,
)
from tests.support.vin import (
    PATTERN as PATTERN,
)
from tests.support.vin import (
    VIN as VIN,
)
from tests.support.vin import (
    catalog as catalog,
)
from tests.support.vin import (
    decoder as decoder,
)

# Synthetic serial with NHTSA's published BMW example pattern; no user's VIN.


@pytest.mark.parametrize("value", ["", "X" * 16, "I" * 17, "O" * 17, "Q" * 17, "*" * 17])
def test_format_rejected_without_network(value):
    with pytest.raises(ValidationError):
        VinRequest(vin=value)


def test_check_digit_matches_known_standard_example():
    assert check_digit("1M8GDM9AXKP042788") == "X"
    assert VinRequest(vin=VIN.lower()).vin == VIN


async def test_decode_post_fields_masking_and_numeric_values():
    async with decoder() as client:
        result = await VinProvider(client).decode(VinRequest(vin=VIN))
    assert result.make == "BMW"
    assert result.engine_liters == Decimal(3)
    assert result.check_digit_matches
    assert result.vin_masked == "*************0000"
    assert VIN not in result.model_dump_json()


async def test_echo_mismatch_rejected():
    async with decoder({"VIN": "X" * 17}) as client:
        with pytest.raises(ProviderError, match="vin_invalid_response"):
            await VinProvider(client).decode(VinRequest(vin=VIN))


async def test_year_mismatch_rejected():
    async with decoder() as client:
        with pytest.raises(ProviderError, match="vin_model_year_mismatch"):
            await VinProvider(client).decode(VinRequest(vin=VIN, model_year=2012))


async def test_upstream_failure_has_no_retry():
    calls = []

    def unavailable(request):
        calls.append(request)
        return httpx.Response(429)

    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as client:
        with pytest.raises(ProviderError, match="vin_provider_unavailable"):
            await VinProvider(client).decode(VinRequest(vin=VIN))
    assert len(calls) == 1


async def test_partial_decode_stops_before_epa():
    async with decoder({"ErrorCode": "6"}) as client:
        result = await VinSelector(VinProvider(client), None).resolve(VinRequest(vin=VIN))
    assert result.status == "partial"
    assert result.vehicle is None
    assert result.upstream_calls["epa_lookup"] == 0


@pytest.mark.parametrize(
    "changes", [{"FuelTypePrimary": "Electric"}, {"ElectrificationLevel": "Plug-in Hybrid"}]
)
async def test_unsupported_powertrain_stops_before_epa(changes):
    async with decoder(changes) as client:
        result = await VinSelector(VinProvider(client), None).resolve(VinRequest(vin=VIN))
    assert result.status == "unsupported"


async def test_unique_epa_match_supplies_mpg_and_grade():
    async with decoder() as client, httpx.AsyncClient(transport=httpx.MockTransport(catalog)) as epa:
        result = await VinSelector(VinProvider(client), VehicleProvider(epa)).resolve(VinRequest(vin=VIN))
    assert result.status == "resolved"
    assert result.vehicle.id == 123
    assert result.vehicle.combined_mpg == 30
    assert result.fuel_recommendation.fuel_type == "premium"
    assert result.fuel_recommendation.octane_aki is None
    assert result.upstream_calls == {"nhtsa_decode": 1, "epa_lookup": 4}


async def test_missing_engine_requires_confirmation():
    async with (
        decoder({"DisplacementL": ""}) as client,
        httpx.AsyncClient(transport=httpx.MockTransport(catalog)) as epa,
    ):
        result = await VinSelector(VinProvider(client), VehicleProvider(epa)).resolve(VinRequest(vin=VIN))
    assert result.status == "needs_input"
    assert result.vehicle is None
    assert result.choices[0].value == "123"


async def test_two_compatible_configurations_require_confirmation():
    def multiple(request):
        if request.url.path.endswith("/menu/options"):
            return httpx.Response(
                200,
                json={
                    "menuItem": [
                        {"text": "Automatic", "value": "123"},
                        {"text": "Manual", "value": "124"},
                    ]
                },
            )
        response = catalog(request)
        if request.url.path.endswith("/124"):
            record = response.json()
            record.update(id="124", trany="Manual 6-spd")
            return httpx.Response(200, json=record)
        return response

    async with decoder() as client, httpx.AsyncClient(transport=httpx.MockTransport(multiple)) as epa:
        result = await VinSelector(VinProvider(client), VehicleProvider(epa)).resolve(VinRequest(vin=VIN))
        assert result.status == "needs_input"
        assert {choice.value for choice in result.choices} == {"123", "124"}
        assert result.vehicle is None
        confirmed = await VinSelector(VinProvider(client), VehicleProvider(epa)).resolve(
            VinRequest(vin=VIN, vehicle_id=124)
        )
        assert confirmed.status == "resolved"
        assert confirmed.vehicle.id == 124


async def test_nonmatching_engine_rejected_even_if_only_candidate():
    async with (
        decoder({"DisplacementL": "2.0"}) as client,
        httpx.AsyncClient(transport=httpx.MockTransport(catalog)) as epa,
    ):
        result = await VinSelector(VinProvider(client), VehicleProvider(epa)).resolve(VinRequest(vin=VIN))
    assert result.status == "no_match"
    assert result.vehicle is None


def test_http_endpoint_without_vin_in_url():
    with TestClient(
        create_app(
            Settings(),
            FixtureProvider(),
            vehicle_provider=VehicleProvider(httpx.AsyncClient(transport=httpx.MockTransport(catalog))),
            vin_provider=VinProvider(decoder()),
        )
    ) as client:
        result = client.post("/v1/vehicles/vin", json={"vin": VIN})
        assert result.status_code == 200
        assert result.json()["status"] == "resolved"
        assert VIN not in result.text
        assert client.post("/v1/vehicles/vin", json={"vin": "invalid"}).status_code == 422


@pytest.mark.parametrize("same_grade", [True, False])
async def test_family_trim_matches_only_correct_body_and_digit_boundary(same_grade):
    def handle(request):
        if request.url.path.endswith("/menu/make"):
            rows = [{"text": "Mercedes-Benz", "value": "Mercedes-Benz"}]
        elif request.url.path.endswith("/menu/model"):
            rows = [
                {"text": n, "value": n}
                for n in ("E400 Coupe", "E400 4matic Coupe", "E400 Convertible", "E4000 Coupe")
            ]
        elif request.url.path.endswith("/menu/options"):
            n = request.url.params["model"]
            assert n in ("E400 Coupe", "E400 4matic Coupe")
            rows = [{"text": "Automatic 9-spd", "value": "201" if n == "E400 Coupe" else "202"}]
        else:
            number = int(request.url.path.rsplit("/", 1)[1])
            return httpx.Response(
                200,
                json={
                    **RECORD,
                    "id": number,
                    "year": 2018,
                    "make": "Mercedes-Benz",
                    "model": "E400 Coupe" if number == 201 else "E400 4matic Coupe",
                    "fuelType1": "Premium Gasoline" if same_grade or number == 201 else "Regular Gasoline",
                    "displ": "3.0",
                    "cylinders": 6,
                    "trany": "Automatic 9-spd",
                    "drive": "Rear-Wheel Drive" if number == 201 else "All-Wheel Drive",
                },
            )
        return httpx.Response(200, json={"menuItem": rows})

    async with (
        decoder(
            {
                "Make": "MERCEDES-BENZ",
                "Model": "E-Class",
                "ModelYear": "2018",
                "Trim": "E 400",
                "DriveType": "",
                "BodyClass": "Coupe",
                "TransmissionStyle": "Automatic",
                "TransmissionSpeeds": "9",
            }
        ) as vins,
        httpx.AsyncClient(transport=httpx.MockTransport(handle)) as epa,
    ):
        result = await VinSelector(VinProvider(vins), VehicleProvider(epa)).resolve(VinRequest(vin=VIN))
    assert result.status == "needs_input"
    assert result.mpg_status == "needs_confirmation"
    assert result.vehicle is None
    assert [c.value for c in result.choices] == ["201", "202"]
    if same_grade:
        assert result.fuel_status == "manufacturer_manual"
        assert result.fuel_recommendation.recommended_octane_aki == 91
        assert result.fuel_recommendation.fuel_type == "premium"
        assert result.fuel_recommendation.octane_aki is None
        assert result.fuel_recommendation.manufacturer_requirement_verified
    else:
        assert result.fuel_status == "unknown"
        assert result.fuel_recommendation is None


async def test_unknown_trim_does_not_broaden_to_unrelated_models():
    async with (
        decoder({"Model": "Unknown Family", "Trim": "Unrelated Badge"}) as vins,
        httpx.AsyncClient(transport=httpx.MockTransport(catalog)) as epa,
    ):
        result = await VinSelector(VinProvider(vins), VehicleProvider(epa)).resolve(VinRequest(vin=VIN))
    assert result.status == "no_match"
    assert result.fuel_recommendation is None
    assert result.mpg_status == "unknown"
