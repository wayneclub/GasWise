import httpx
import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.domain.vehicles.fuel_policy import resolve_fuel_query
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.services.pricing.search import SearchService
from tests.support.comparison import Prices, quote, select
from tests.support.vin import RECORD


def test_verified_threshold_accepts_higher_and_rejects_lower():
    for number, expected in [(89, 0), (91, 1), (93, 1)]:
        selected, _, _ = select([quote(octane=number)], required_octane=91, octane_policy="verified_only")
        assert len(selected) == expected


def test_california_grade_estimate_is_visible_and_strict_mode_can_exclude():
    station = quote(address="Los Angeles, CA 90029")
    selected, _, warnings = select([station], required_octane=91)
    assert len(selected) == 1
    assert selected[0].station.octane is None
    evidence = selected[0].evidence[0].octane_inference
    assert evidence["estimated_octane"] == 91
    assert not evidence["station_verified"]
    assert evidence["source_urls"]
    assert warnings
    assert select([station], required_octane=91, octane_policy="verified_only")[0] == []
    assert select([station], required_octane=93)[0] == []


def test_state_fallback_and_conservative_national_ranges():
    # Colorado regular can be 85; never assume that all Regular is 87.
    st = quote(address="Denver, CO 80202").model_copy(update={"fuel_type": "regular"})
    assert select([st], fuel_type="regular", required_octane=87, current_state="CA")[0] == []
    rows, _, _ = select([quote()], required_octane=91, current_state="CA")
    assert rows[0].station.octane_inference["state_basis"] == "origin_state_fallback"
    assert select([quote()], required_octane=91)[0] == []
    assert select([quote()], required_octane=93, current_state="NY")[0] == []


def test_explicit_pump_rating_wins_over_regional_guess():
    assert len(select([quote(octane=93, address="LA, CA 90029")], required_octane=93)[0]) == 1
    assert select([quote(octane=89, address="LA, CA 90029")], required_octane=91)[0] == []


async def test_scoped_manufacturer_rule_automatically_applies_normal_target():
    def handler(request):
        return httpx.Response(
            200,
            json={
                **RECORD,
                "id": "38902",
                "year": "2018",
                "make": "Mercedes-Benz",
                "model": "E400 Coupe",
                "displ": "3.0",
                "cylinders": "6",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        v = await VehicleProvider(c).vehicle(38902)
    requirement = v.fuel_recommendation
    assert requirement.source == "manufacturer_manual"
    assert requirement.recommended_octane_aki == 91
    assert requirement.minimum_octane_aki is None
    assert requirement.temporary_octane_aki == 87
    q = resolve_fuel_query(Search(origin=Point(lat=34, lng=-118), required_octane=87), v)
    assert q.required_octane == 91
    assert resolve_fuel_query(q.model_copy(update={"required_octane": 93}), v).required_octane == 93


async def test_unknown_vehicle_keeps_no_numeric_requirement():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=RECORD))
    ) as c:
        v = await VehicleProvider(c).vehicle(int(RECORD["id"]))
    assert v.fuel_recommendation.recommended_octane_aki is None


async def test_search_applies_vehicle_target_before_price_ranking():
    def handler(request):
        return httpx.Response(
            200,
            json={
                **RECORD,
                "id": "38902",
                "year": "2018",
                "make": "Mercedes-Benz",
                "model": "E400 Coupe",
                "displ": "3.0",
                "cylinders": "6",
            },
        )

    records = [
        quote(station_id="lower", octane=89, price="4.00"),
        quote(station_id="93", octane=93, price="5.00"),
        quote(station_id="regional", address="Los Angeles, CA 90029", price="4.90"),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        service = SearchService(Prices(records), "google", VehicleProvider(c))
        result = await service.search(Search(origin=records[0].location, vehicle_id=38902))
    assert result.applied_octane_aki == 91
    assert {r.station.id for r in result.results} == {"93", "regional"}
    assert result.octane_policy == "regional_estimate"
    assert any("regional estimate" in w for w in result.warnings)


@pytest.mark.parametrize(
    "changes",
    [
        {"year": 2019},
        {"model": "E400 Convertible"},
        {"make": "BMW"},
        {"engine_liters": 2},
        {"cylinders": 4},
        {"fuel_type": "Regular Gasoline"},
    ],
)
async def test_manufacturer_rule_does_not_leak_to_unverified_configurations(changes):
    from gaswise.domain.vehicles.requirements import manufacturer_fuel_requirement

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    **RECORD,
                    "id": 38902,
                    "year": 2018,
                    "make": "Mercedes-Benz",
                    "model": "E400 Coupe",
                    "displ": "3.0",
                    "cylinders": 6,
                },
            )
        )
    ) as c:
        v = await VehicleProvider(c).vehicle(38902)
    assert manufacturer_fuel_requirement(v.model_copy(update=changes)) is None


async def test_strict_snapshot_rerank_excludes_estimates_without_network():
    from gaswise.contracts.search import RankOptions
    from gaswise.contracts.smart import SmartRerank, SmartSearch
    from gaswise.services.pricing.smart import SmartService
    from tests.support.smart import CountingProvider

    class RegionalProvider(CountingProvider):
        async def stations(self, query):
            rows = await super().stations(query)
            return [r.model_copy(update={"octane": None, "address": "Los Angeles, CA 90029"}) for r in rows]

    provider = RegionalProvider()
    service = SmartService(b"octane-test", "demo", demo=provider)
    first = await service.search(
        SmartSearch(
            origin=Point(lat=34, lng=-118), required_octane=91, current_state="CA", calculate_routes=True
        )
    )
    assert first.ranking.results
    counts = provider.searches, provider.routes
    strict = await service.rerank(
        SmartRerank(
            snapshot=first.snapshot,
            signature=first.signature,
            options=RankOptions(octane_policy="verified_only"),
        )
    )
    assert strict.ranking.results == []
    assert strict.ranking.applied_octane_aki == 91
    assert (provider.searches, provider.routes) == counts
    assert not any(strict.upstream_calls.values())
