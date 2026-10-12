import httpx
import pytest
from pydantic import ValidationError

from gaswise.contracts.vehicles import FuelAssessmentRequest, VehicleMenu
from gaswise.domain.ports import ProviderError
from gaswise.domain.vehicles.requirements import manufacturer_fuel_requirement
from gaswise.providers.vehicles.hertz import HertzProvider
from gaswise.providers.vehicles.vin import VinProvider
from gaswise.services.vehicles.fuel_assessment import assess_fuel
from tests.support.vehicle_requirements_2021 import PROFILES
from tests.support.vin import DECODE, VIN

URL = "https://www.hertzcarsales.com/used/BMW/2021-BMW-M4-example.htm"


class Catalog:
    async def vehicle(self, vehicle_id):
        v = PROFILES[vehicle_id].model_copy(deep=True)
        v.fuel_recommendation = manufacturer_fuel_requirement(v) or v.fuel_recommendation
        return v

    async def menu(self, kind, **params):
        value = "BMW" if kind == "make" else "M4 Coupe" if kind == "model" else "43559"
        if kind == "options" and params["year"] != 2021:
            value = "123"
        return VehicleMenu(items=[{"text": value, "value": value}])


@pytest.mark.parametrize(
    "vehicle_id,target,basis",
    [
        (43559, 91, "manufacturer_minimum"),
        (42900, 89, "manufacturer_minimum"),
        (43515, 91, "manufacturer_normal_recommendation"),
        (42597, None, "unresolved"),
    ],
)
async def test_one_target_is_not_performance_recommendation_or_fake_minimum(vehicle_id, target, basis):
    result = await assess_fuel(FuelAssessmentRequest(vehicle_id=vehicle_id), Catalog(), None, None)
    assert result.target_octane_aki == target
    assert result.target_basis == basis
    assert result.hertz_status == "not_requested"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.hertzcarsales.com/used/a.htm",
        "https://evil.example/used/a.htm",
        "https://www.hertzcarsales.com@evil.example/used/a.htm",
        "https://www.hertzcarsales.com/used/a.htm?redirect=x",
        "https://[broken",
    ],
)
def test_external_or_non_listing_urls_rejected(url):
    with pytest.raises(ValidationError):
        FuelAssessmentRequest(vehicle_id=43559, hertz_listing_url=url)


async def test_listing_parser_and_no_redirect_or_script_evidence():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            text="<script>Recommended fuel: Diesel VIN: 00000000000000000</script>"
            "<div>VIN: 11111111111111111</div><li>Recommended fuel: Premium Unleaded</li>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        vin, grade = await HertzProvider(c).listing(URL)
    assert vin == "1" * 17
    assert grade == "premium unleaded"
    assert len(seen) == 1


async def test_hertz_failure_preserves_verified_target():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403))) as c:
        result = await assess_fuel(
            FuelAssessmentRequest(vehicle_id=43559, hertz_listing_url=URL), Catalog(), None, HertzProvider(c)
        )
    assert result.hertz_status == "unavailable"
    assert result.target_octane_aki == 91
    assert result.hertz_recommended_grade is None


@pytest.mark.parametrize(
    "year,grade,status",
    [
        (2021, "Premium Unleaded", "matched"),
        (2020, "Premium Unleaded", "mismatch"),
        (2021, "Regular Unleaded", "matched"),
    ],
)
async def test_listing_identity_checked_and_grade_conflict_cannot_override_minimum(year, grade, status):
    def handler(request):
        if request.url.host == "www.hertzcarsales.com":
            return httpx.Response(200, text=f"<div>VIN: {VIN}</div><li>Recommended fuel: {grade}</li>")
        return httpx.Response(
            200,
            json={
                "Results": [
                    {
                        **DECODE,
                        "Model": "M4",
                        "ModelYear": str(year),
                        "Trim": "",
                        "DriveType": "Rear-Wheel Drive",
                        "BodyClass": "Coupe",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        result = await assess_fuel(
            FuelAssessmentRequest(vehicle_id=43559, hertz_listing_url=URL),
            Catalog(),
            VinProvider(c),
            HertzProvider(c),
        )
    assert result.target_octane_aki == 91
    assert result.hertz_status == status
    assert (result.hertz_recommended_grade is not None) == (status == "matched")
    if grade == "Regular Unleaded":
        assert any("differs" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    "body,status",
    [
        ("VIN: 11111111111111111 Recommended fuel: Premium Unleaded VIN: 22222222222222222", 200),
        ("VIN: 11111111111111111 Recommended fuel: Premium Unleaded", 302),
    ],
)
async def test_ambiguous_or_redirecting_listing_rejected(body, status):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text=body))
    ) as c:
        with pytest.raises(ProviderError):
            await HertzProvider(c).listing(URL)
