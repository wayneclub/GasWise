from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point, Route, Station
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app


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
                payment_type="credit",
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
