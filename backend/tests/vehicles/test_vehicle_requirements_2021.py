import httpx
import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.domain.vehicles.fuel_policy import resolve_fuel_query
from gaswise.domain.vehicles.requirements import manufacturer_fuel_requirement
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.services.pricing.search import SearchService
from tests.support.comparison import Prices, quote
from tests.support.vehicle_requirements_2021 import (
    PROFILES as PROFILES,
)


@pytest.mark.parametrize(
    "vehicle_id,minimum,recommended,mpg",
    [
        (43515, None, 91, 27),
        (43348, None, 91, 27),
        (42849, 89, 91, 27),
        (42899, 89, 91, 25),
        (42900, 89, 93, 23),
        (43559, 91, 93, 19),
        (43560, 91, 93, 19),
    ],
)
async def test_real_epa_profiles_through_provider_and_search(vehicle_id, minimum, recommended, mpg):
    profile = PROFILES[vehicle_id]
    raw = {
        "id": profile.id,
        "year": profile.year,
        "make": profile.make,
        "model": profile.model,
        "trany": profile.transmission,
        "drive": profile.drive,
        "displ": str(profile.engine_liters),
        "cylinders": profile.cylinders,
        "fuelType1": profile.fuel_type,
        "city08": str(profile.city_mpg),
        "highway08": str(profile.highway_mpg),
        "comb08": str(profile.combined_mpg),
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=raw))) as c:
        provider = VehicleProvider(c)
        v = await provider.vehicle(vehicle_id)
        requirement = v.fuel_recommendation
        assert requirement.minimum_octane_aki == minimum
        assert requirement.recommended_octane_aki == recommended
        assert requirement.source == "manufacturer_manual"
        assert requirement.source_urls
        assert v.combined_mpg == mpg
        floor = minimum or recommended
        records = [quote(station_id=str(aki), octane=aki) for aki in (87, 89, 91, 93)]
        service = SearchService(Prices(records), "google", provider)
        result = await service.search(
            Search(origin=records[0].location, vehicle_id=vehicle_id, octane_policy="verified_only")
        )
        assert result.applied_octane_aki == floor
        assert {r.station.id for r in result.results} == {
            str(aki) for aki in (87, 89, 91, 93) if aki >= floor
        }
        assert (
            resolve_fuel_query(Search(origin=Point(lat=34, lng=-118), required_octane=93), v).required_octane
            == 93
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"year": 2020},
        {"year": 2022},
        {"model": "M440i xDrive Coupe"},
        {"model": "M4 Convertible"},
        {"engine_liters": 2},
        {"cylinders": 4},
        {"powertrain": "hybrid"},
        {"fuel_type": "Regular Gasoline"},
    ],
)
def test_m4_scope_never_leaks(changes):
    assert manufacturer_fuel_requirement(PROFILES[43559].model_copy(update=changes)) is None


def test_c300_body_and_x3_full_m_are_separate_scopes():
    assert manufacturer_fuel_requirement(PROFILES[43515].model_copy(update={"model": "C300 Coupe"})) is None
    assert manufacturer_fuel_requirement(PROFILES[42597]) is None
