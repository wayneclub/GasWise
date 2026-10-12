from decimal import Decimal

import pytest
from pydantic import ValidationError

from gaswise.contracts.common import Point
from gaswise.contracts.search import RankOptions, Search
from gaswise.contracts.smart import SmartRerank, SmartSearch
from gaswise.domain.pricing.fuel import fuel_model
from gaswise.services.pricing.smart import SmartService
from tests.support.service import client
from tests.support.smart import CountingProvider


def test_unequal_tank_intervals_use_fuel_balance_not_average_mpg():
    query = Search(
        origin=Point(lat=34, lng=-118),
        fuel_cycles=[
            {"distance_miles": "100", "consumed_gallons": "10"},
            {"distance_miles": "600", "consumed_gallons": "20"},
        ],
    )
    model = fuel_model(query)
    assert model.mpg_used == Decimal(700) / 30
    assert model.mpg_used != Decimal(20)  # arithmetic mean of 10 and 30 MPG is wrong
    assert model.calibration_cycles == 2
    assert model.basis == "full_tank_calibrated_estimate"


def test_calibration_changes_ranking_and_all_cost_bases():
    with client() as api:
        response = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "mpg": "20",
                "fuel_cycles": [{"distance_miles": "100", "consumed_gallons": "10"}],
            },
        )
    assert response.status_code == 200
    data = response.json()
    row = data["results"][0]
    assert row["station"]["name"] == "Chevron"
    assert row["actual_fuel_cost"] == "64.92"
    assert row["mpg_used"] == "10"
    assert Decimal(row["detour_fuel_gallons"]) == Decimal("0.16")
    assert Decimal(row["baseline_fuel_gallons"]) == 0
    assert row["fuel_model"]["route_specific_efficiency"] is False
    assert row["price_comparison"]["comparable_cost_min"] == row["actual_fuel_cost"]
    assert data["recommendations"]["cheapest_overall"]["station"]["name"] == "Chevron"
    gulf = next(row for row in data["results"] if row["station"]["name"] == "Gulf")
    assert Decimal(gulf["break_even"]["fuel_only_gallons"]) > Decimal(10)


def test_calibrated_on_route_subtracts_baseline_fuel():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "destination": {"lat": 35, "lng": -118},
                "trip_mode": "on_route",
                "fuel_cycles": [{"distance_miles": "100", "consumed_gallons": "10"}],
            },
        ).json()
    row = data["results"][0]
    assert Decimal(row["baseline_fuel_gallons"]) == Decimal(10)
    assert abs(Decimal(row["route_fuel_gallons"]) - Decimal("10.16")) < Decimal("1e-12")
    assert abs(Decimal(row["detour_fuel_gallons"]) - Decimal("0.16")) < Decimal("1e-12")


@pytest.mark.parametrize(
    "cycle",
    [
        {"distance_miles": 0, "consumed_gallons": 10},
        {"distance_miles": 100, "consumed_gallons": -1},
        {"distance_miles": "NaN", "consumed_gallons": 10},
    ],
)
def test_invalid_consumption_cycles_rejected(cycle):
    with pytest.raises(ValidationError):
        Search(origin=Point(lat=34, lng=-118), fuel_cycles=[cycle])


async def test_calibration_rerank_needs_zero_provider_calls_and_can_be_cleared():
    provider = CountingProvider()
    service = SmartService(b"test", "demo", demo=provider)
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    counts = provider.searches, provider.routes
    calibrated = await service.rerank(
        SmartRerank(
            snapshot=first.snapshot,
            signature=first.signature,
            options=RankOptions(fuel_cycles=[{"distance_miles": 100, "consumed_gallons": 10}]),
        )
    )
    assert calibrated.ranking.results[0].station.name == "Chevron"
    reset = await service.rerank(
        SmartRerank(
            snapshot=calibrated.snapshot,
            signature=calibrated.signature,
            options=RankOptions(fuel_cycles=[]),
        )
    )
    assert reset.ranking.results[0].station.name == "Arco"
    assert reset.ranking.results[0].fuel_consumption_basis == "user_mpg_estimate"
    assert not any(calibrated.upstream_calls.values())
    assert not any(reset.upstream_calls.values())
    assert (provider.searches, provider.routes) == counts
