import math
from datetime import UTC, datetime
from decimal import Decimal

from gaswise.models import Point, Route, Search, Station


class DemoProvider:
    """Synthetic stations and routes. Never represent these as live observations."""

    async def stations(self, query: Search) -> list[Station]:
        now = datetime.now(UTC)
        samples = [
            ("Chevron", "6.39", 0.008),
            ("Shell", "6.19", 0.025),
            ("Arco", "5.99", 0.05),
            ("Gulf", "5.79", 0.09),
        ]
        return [
            Station(
                id=f"demo-{i}",
                name=name,
                location=Point(lat=max(-90, min(90, query.origin.lat + offset)), lng=query.origin.lng),
                price_per_gallon=Decimal(price),
                fuel_type=query.fuel_type,
                octane=91 if query.fuel_type == "premium" else None,
                fetched_at=now,
                price_updated_at=now,
                source="synthetic",
                payment_type=query.payment_type,
            )
            for i, (name, price, offset) in enumerate(samples)
            if offset * 111320 <= query.radius_meters
        ][: query.max_results]

    async def route(self, origin: Point, destination: Point, via: Point | None = None) -> Route:
        def distance(a, b):
            phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
            dphi, dlambda = phi2 - phi1, math.radians(b.lng - a.lng)
            h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            return 6371000 * 2 * math.asin(math.sqrt(min(1, h))) * 1.25

        meters = distance(origin, via) + distance(via, destination) if via else distance(origin, destination)
        return Route(
            distance_meters=meters, duration_seconds=meters / 10, source="synthetic_distance_estimate"
        )


class DemoComparisonSource:
    """Synthetic second source, never passed off as a real GasBuddy observation."""

    async def stations(self, query: Search) -> list[Station]:
        stations = await DemoProvider().stations(query)
        return [
            s.model_copy(
                update={
                    "source": "gasbuddy_demo",
                    "canonical_id": f"synthetic:{s.id}",
                    "price_per_gallon": s.price_per_gallon
                    + (Decimal("0.30") if s.name == "Gulf" else Decimal("0.02")),
                }
            )
            for s in stations
        ]
