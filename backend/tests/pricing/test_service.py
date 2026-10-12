from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Route
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from tests.support.service import (
    FixtureProvider as FixtureProvider,
)
from tests.support.service import (
    client as client,
)


def test_true_cost_beats_pump_price():
    with client() as api:
        data = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}}).json()
    assert [row["station"]["name"] for row in data["results"]] == ["Arco", "Gulf", "Shell", "Chevron"]
    assert data["results"][0]["actual_fuel_cost"] == "62.90"
    assert data["results"][1]["actual_fuel_cost"] == "63.11"


def test_only_extra_route_counts():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "destination": {"lat": 35, "lng": -118},
                "trip_mode": "on_route",
            },
        ).json()
    assert data["results"][0]["detour_miles"] == "10.000"
    assert data["results"][0]["actual_fuel_cost"] == "62.90"


def test_time_value_changes_choice():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={"origin": {"lat": 34, "lng": -118}, "strategy": "best_value", "time_value_per_hour": "60"},
        ).json()
    assert data["results"][0]["station"]["name"] == "Chevron"
    assert data["results"][0]["time_cost"] == "13.00"


@pytest.mark.parametrize(
    "provider,extra",
    [(FixtureProvider(stale=True), {}), (FixtureProvider(unknown_octane=True), {"required_octane": 91})],
)
def test_missing_eligibility_does_not_get_ranked(provider, extra):
    with client(provider) as api:
        data = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}, **extra}).json()
    assert data["results"] == []
    assert data["excluded_count"] == 4


def test_failed_station_route_is_excluded():
    with client(FixtureProvider(fail_route=True)) as api:
        data = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}}).json()
    assert data["excluded_count"] == 1
    assert len(data["results"]) == 3


@pytest.mark.parametrize(
    "extra",
    [
        {"mpg": 0},
        {"gallons": -1},
        {"trip_mode": "on_route"},
        {"origin": {"lat": 91, "lng": 0}},
        {"max_results": 101},
    ],
)
def test_invalid_input(extra):
    with client() as api:
        assert (
            api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}, **extra}).status_code
            == 422
        )


def test_auth_and_no_cache():
    with client(token="secret") as api:
        assert api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}}).status_code == 401
        response = api.post(
            "/v1/recommendations",
            headers={"Authorization": "Bearer secret"},
            json={"origin": {"lat": 34, "lng": -118}},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"


def test_google_mode_requires_credentials():
    with pytest.raises(ValueError):
        Settings(mode="google")


def test_stream_refresh_failure_closes_without_fabricating_snapshot(monkeypatch):
    import gaswise.api.recommendations as main

    class FailsAfterFirst(FixtureProvider):
        calls = 0

        async def stations(self, query):
            self.calls += 1
            if self.calls > 1:
                raise ProviderError("upstream_unavailable")
            return await super().stations(query)

    async def no_wait(_):
        pass

    monkeypatch.setattr(main, "sleep", no_wait)
    provider = FailsAfterFirst()
    with TestClient(create_app(Settings(refresh_seconds=60), provider)) as api:
        response = api.post("/v1/recommendations/stream", json={"origin": {"lat": 34, "lng": -118}})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: snapshot") == 1
    assert "event: error" in response.text
    assert "upstream_unavailable" in response.text
    assert "event: end" in response.text
    assert provider.calls == 2


def test_stream_initial_failure_retains_http_error():
    class Unavailable(FixtureProvider):
        async def stations(self, query):
            raise ProviderError("upstream_unavailable")

    with client(Unavailable()) as api:
        response = api.post("/v1/recommendations/stream", json={"origin": {"lat": 34, "lng": -118}})
    assert response.status_code == 502


def test_break_even_threshold_is_relative_to_nearest():
    with client() as api:
        result = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}}).json()
    # (10/20*5.99 - 1.6/20*6.39) / (6.39-5.99), before money rounding.
    assert result["results"][0]["break_even_gallons_vs_nearest"] == "6.21"


def test_strategy_cards_use_same_candidates_before_result_limit():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "max_results": 1,
                "time_value_per_hour": "60",
            },
        ).json()
    assert len(data["results"]) == 1
    cards = data["recommendations"]
    assert cards["cheapest_overall"]["station"]["name"] == "Arco"
    assert cards["fastest_stop"]["station"]["name"] == "Chevron"
    assert cards["best_value"]["station"]["name"] == "Chevron"
    assert cards["on_my_route"]["station"] is None
    assert cards["on_my_route"]["unavailable_reason"] == "requires_on_route_trip"


def test_break_even_explains_money_and_time_separately():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "time_value_per_hour": "60",
            },
        ).json()
    arco = data["results"][0]["break_even"]
    assert arco["reference_station_name"] == "Chevron"
    assert arco["additional_fuel_cost"] == "2.48"
    assert arco["additional_time_cost"] == "18.00"
    assert Decimal(arco["fuel_only_gallons"]) == Decimal("6.2095")
    assert Decimal(arco["including_time_gallons"]) == Decimal("51.2095")
    assert arco["fuel_savings_at_requested_gallons"] == "1.52"
    assert arco["generalized_savings_at_requested_gallons"] == "-16.48"
    assert arco["worthwhile_fuel_only"] is True
    assert arco["worthwhile_including_time"] is False


def test_break_even_exact_threshold_is_a_tie():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "gallons": "6.2095",
            },
        ).json()
    arco = next(row for row in data["results"] if row["station"]["name"] == "Arco")
    assert arco["break_even"]["fuel_savings_at_requested_gallons"] == "0.00"
    assert arco["break_even"]["worthwhile_fuel_only"] is False


def test_on_route_card_uses_incremental_route():
    with client() as api:
        data = api.post(
            "/v1/recommendations",
            json={
                "origin": {"lat": 34, "lng": -118},
                "destination": {"lat": 35, "lng": -118},
                "trip_mode": "on_route",
            },
        ).json()
    assert data["recommendations"]["on_my_route"]["actual_fuel_cost"] == "62.90"


def test_no_eligible_candidates_has_no_strategy_winners():
    with client(FixtureProvider(stale=True)) as api:
        data = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}}).json()
    assert all(card["station"] is None for card in data["recommendations"].values())


def test_strategy_cards_do_not_acquire_extra_prices_or_routes():
    class Counted(FixtureProvider):
        price_calls = 0
        route_calls = 0

        async def stations(self, query):
            self.price_calls += 1
            return await super().stations(query)

        async def route(self, origin, destination, via=None):
            self.route_calls += 1
            return await super().route(origin, destination, via)

    provider = Counted()
    with client(provider) as api:
        response = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}})
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 4
    assert provider.price_calls == 1
    assert provider.route_calls == 4


def test_subcent_cost_difference_is_not_overridden_by_faster_drive():
    class Subcent(FixtureProvider):
        async def stations(self, query):
            rows = (await super().stations(query))[:2]
            rows[0].price_per_gallon = Decimal("5.0004")
            rows[1].price_per_gallon = Decimal("5.0001")
            return rows

        async def route(self, origin, destination, via=None):
            return Route(distance_meters=0, duration_seconds=0 if via.lat == 34 else 60, source="fixture")

    with client(Subcent()) as api:
        data = api.post("/v1/recommendations", json={"origin": {"lat": 34, "lng": -118}}).json()
    assert [row["actual_fuel_cost"] for row in data["results"]] == ["50.00", "50.00"]
    assert data["results"][0]["station"]["name"] == "Shell"
    assert data["recommendations"]["fastest_stop"]["station"]["name"] == "Chevron"
