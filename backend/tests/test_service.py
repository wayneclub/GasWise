from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gaswise.main import create_app
from gaswise.models import Point, Route, Station
from gaswise.providers.base import ProviderError
from gaswise.settings import Settings


class FixtureProvider:
    def __init__(self, stale=False, unknown_octane=False, fail_route=False):
        self.stale, self.unknown_octane, self.fail_route = stale, unknown_octane, fail_route

    async def stations(self, query):
        now = datetime.now(UTC)
        return [
            Station(
                id=name,
                name=name,
                location=Point(lat=34 + index * 0.001, lng=-118),
                fuel_type="premium",
                octane=None if self.unknown_octane else 91,
                price_per_gallon=Decimal(price),
                fetched_at=now,
                source="fixture",
                price_updated_at=now - timedelta(days=2) if self.stale else now,
            )
            for index, (name, price) in enumerate(
                [("Chevron", "6.39"), ("Shell", "6.19"), ("Arco", "5.99"), ("Gulf", "5.79")]
            )
        ]

    async def route(self, origin, destination, via=None):
        if via is None:
            return Route(distance_meters=100 * 1609.344, duration_seconds=6000, source="fixture")
        if self.fail_route and round((via.lat - 34) * 1000) == 3:
            raise ProviderError("route_unavailable")
        distance = [1.6, 5, 10, 18][round((via.lat - 34) * 1000)] * 1609.344
        duration = [8, 16, 26, 44][round((via.lat - 34) * 1000)] * 60
        if origin != destination:
            distance += 100 * 1609.344
            duration += 6000
        return Route(distance_meters=distance, duration_seconds=duration, source="fixture")


def client(provider=None, token=""):
    return TestClient(create_app(Settings(api_token=token), provider or FixtureProvider()))


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
        {"max_results": 11},
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
    import gaswise.main as main

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
    assert result["results"][0]["break_even_gallons_vs_nearest"] == "6.23"
