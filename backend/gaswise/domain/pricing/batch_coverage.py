"""Deterministic, rollback-friendly planning for fixed public collection bases."""

import math

from gaswise.contracts.common import Point
from gaswise.domain.pricing.collection_bases import BASES
from gaswise.domain.pricing.comparison import distance_meters

LEGACY_RADIUS_METERS = 10_000
MAX_ISOLATED_RADIUS_METERS = 20_000


def requested_radii(
    bases,
    *,
    strategy="isolated_radius_v1",
    base_radius=LEGACY_RADIUS_METERS,
    max_radius=MAX_ISOLATED_RADIUS_METERS,
):
    """Return query radii without changing job count or per-job request budgets.

    The adaptive strategy only fills the empty half-gap to the nearest configured
    base. Dense regions retain the legacy radius, while isolated edge/corridor
    bases expand up to a conservative cap.
    """
    if strategy not in {"legacy", "isolated_radius_v1"}:
        raise ValueError("Unknown base collection coverage strategy")
    if not 100 <= base_radius <= max_radius <= 50_000:
        raise ValueError("Invalid base collection radius bounds")
    points = {base: Point(lat=BASES[base][0], lng=BASES[base][1]) for base in bases}
    result = {}
    for base, point in points.items():
        radius = float(base_radius)
        if strategy != "legacy" and len(points) > 1:
            nearest = min(distance_meters(point, other) for key, other in points.items() if key != base)
            radius = min(float(max_radius), max(radius, nearest / 2))
        result[base] = radius
    return result


def circle_area_km2(radius_meters):
    return math.pi * (radius_meters / 1000) ** 2


def run_metrics(quotes):
    """Sanitized station-yield metrics; no raw payload or query location is retained."""
    provider = {(quote.source, str(quote.id)) for quote in quotes}
    canonical = {
        quote.canonical_id or f"{quote.source}:{quote.id}"
        for quote in quotes
    }
    return {
        "canonical_count": len(canonical),
        "located_count": sum(quote.location is not None for quote in quotes),
        "priced_count": sum(quote.price_per_gallon > 0 for quote in quotes),
        "inventory_overlap_count": len({
            quote.canonical_id for quote in quotes
            if quote.canonical_id and quote.canonical_id.startswith("google_places:")
        }),
        "station_keys": [
            {"source": source, "station_id": station_id, "canonical_id": next(
                (quote.canonical_id for quote in quotes
                 if quote.source == source and str(quote.id) == station_id and quote.canonical_id),
                None,
            )}
            for source, station_id in sorted(provider)
        ],
    }

def simulated_area(radii, *, cell_km=1.0):
    """Deterministic equal-area local grid estimate for plan comparisons."""
    if cell_km <= 0:
        raise ValueError("Coverage simulation cell size must be positive")
    mean_lat = sum(BASES[base][0] for base in radii) / len(radii)
    cos_lat = math.cos(math.radians(mean_lat))
    counts = {}
    projected = {}
    for base in radii:
        lat, lng = BASES[base]
        projected[base] = (lng * 111.320 * cos_lat, lat * 110.574)
    for base, radius_meters in radii.items():
        x, y = projected[base]
        radius = radius_meters / 1000
        x0, x1 = math.floor((x - radius) / cell_km), math.ceil((x + radius) / cell_km)
        y0, y1 = math.floor((y - radius) / cell_km), math.ceil((y + radius) / cell_km)
        for ix in range(x0, x1 + 1):
            for iy in range(y0, y1 + 1):
                cx, cy = (ix + .5) * cell_km, (iy + .5) * cell_km
                if (cx - x) ** 2 + (cy - y) ** 2 <= radius ** 2:
                    counts[(ix, iy)] = counts.get((ix, iy), 0) + 1
    area = cell_km ** 2
    gaps = []
    for base, point in projected.items():
        nearest_base, nearest_gap = None, float("inf")
        for other, other_point in projected.items():
            if other == base:
                continue
            separation = math.dist(point, other_point) - (radii[base] + radii[other]) / 1000
            if separation < nearest_gap:
                nearest_base, nearest_gap = other, separation
        if nearest_base is not None and nearest_gap > 0:
            gaps.append({"between": sorted((base, nearest_base)), "gap_km": round(nearest_gap, 1)})
    unique_gaps = {tuple(row["between"]): row for row in gaps}
    return {
        "covered_km2": round(len(counts) * area, 1),
        "overlap_km2": round(sum(value > 1 for value in counts.values()) * area, 1),
        "overlap_share": round(sum(value > 1 for value in counts.values()) / len(counts), 4),
        "max_overlap": max(counts.values(), default=0),
        "largest_gaps": sorted(unique_gaps.values(), key=lambda row: row["gap_km"], reverse=True)[:10],
    }
