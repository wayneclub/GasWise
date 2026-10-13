"""Explicit geometric fallback for stations outside the precise route budget."""

from gaswise.contracts.common import Route
from gaswise.domain.pricing.comparison import distance_meters


def estimate_route(origin, destination, via, baseline):
    """Geometric fallback: 1.3 road factor and 25 mph, without traffic evidence."""
    direct = distance_meters(origin, destination)
    via_distance = distance_meters(origin, via) + distance_meters(via, destination)
    extra = max(0, via_distance - direct) * 1.3
    return Route(
        distance_meters=baseline.distance_meters + extra,
        duration_seconds=baseline.duration_seconds + extra / (25 * 1609.344 / 3600),
        source="straight_line_estimate",
        duration_basis="geometric_estimate",
    )


