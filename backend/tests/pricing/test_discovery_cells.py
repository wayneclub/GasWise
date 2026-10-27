import math
import random

from gaswise.contracts.common import Point
from gaswise.contracts.smart import SmartSearch
from gaswise.contracts.sources import MAPS_WEB_PAGE_SIZE, MapsWebPrices, MapsWebStation
from gaswise.domain.pricing.cells import Coverage
from gaswise.domain.pricing.comparison import distance_meters
from gaswise.services.pricing.smart import SmartService

ORIGIN = Point(lat=34.04, lng=-118.27)


def field(count, spread, seed=1):
    """Synthetic stations, denser towards the origin like a downtown."""
    rnd = random.Random(seed)
    points = []
    for _ in range(count):
        meters, angle = abs(rnd.gauss(0, spread)), rnd.random() * 2 * math.pi
        points.append(Point(
            lat=ORIGIN.lat + meters * math.cos(angle) / 111320,
            lng=ORIGIN.lng + meters * math.sin(angle) / (111320 * math.cos(math.radians(ORIGIN.lat))),
        ))
    return points


class NearestFirstMaps:
    """Website-shaped fixture: one page per viewport, ranked by distance plus relevance noise.

    Noise grows with the viewport, as the production probe showed: a wide viewport
    filled its page within 4.2km yet skipped stations 0.6km and 1.5km away.
    """

    def __init__(self, points):
        self.points, self.queries = points, []
        rnd = random.Random(7)
        self.relevance = {id(p): rnd.random() for p in points}

    async def prices(self, query):
        self.queries.append(query)
        page = sorted(
            self.points,
            key=lambda p: distance_meters(query.origin, p) + self.relevance[id(p)] * 0.5 * query.radius_meters,
        )[:MAPS_WEB_PAGE_SIZE]
        inventory = [
            MapsWebStation(place_id=f"{p.lat:.6f},{p.lng:.6f}", name="Station", location=p, address=None,
                           distance_meters=distance_meters(query.origin, p), available_fuel_types=["regular"])
            for p in page if distance_meters(query.origin, p) <= query.radius_meters
        ]
        return MapsWebPrices(
            stations=[], inventory=inventory, warnings=[], candidate_count=len(page),
            candidate_reach_meters=max((distance_meters(query.origin, p) for p in page), default=None),
        )


def search(budget, origin=ORIGIN):
    return SmartSearch(origin=origin, fuel_type="regular", radius_meters=8047, discovery_tiles=budget)


def test_only_a_page_that_spills_past_its_radius_proves_the_disk():
    coverage = Coverage(ORIGIN, 9600)
    assert coverage.record(ORIGIN, 1600, 12, 12, 900, 20)  # short page
    # Production: a 19-place page inside its radius was a full page missing one record, not sparse.
    assert not coverage.record(ORIGIN, 12800, 19, 19, 4000, 20)
    # Production (Bakersfield): a wide page spilling past 10km still missed most stations.
    assert not coverage.record(ORIGIN, 12800, 20, 19, 14000, 20)
    assert coverage.record(ORIGIN, 1600, 20, 13, 2500, 20)  # full page reaching beyond its radius
    # Production probe: a wide viewport filled within 4.2km yet skipped stations at 628m and 1472m.
    assert not coverage.record(ORIGIN, 12800, 20, 20, 4173, 20)
    # Shrinks one ladder step per wave: one wide page is not a reliable density estimate.
    assert coverage.query_radius == 3200
    first, radius = coverage.wave(4)
    assert radius == 3200 and len(first) >= 3
    assert all(distance_meters(a, b) > 4800 for i, a in enumerate(first) for b in first[i + 1:])


async def test_sparse_area_is_proven_by_one_whole_area_request():
    maps = NearestFirstMaps(field(12, 5000))
    result = await SmartService(b"test", "prices_only", maps_web=maps).search(search(20))
    assert len(maps.queries) == result.upstream_calls["google_maps_web_search"] == 1
    assert result.snapshot.discovery_area_covered == 1
    assert len(result.snapshot.inventory) == sum(distance_meters(ORIGIN, p) <= 8047 * 1.2 for p in maps.points)


async def test_dense_area_expands_in_waves_and_reports_unproven_area():
    points = field(400, 6000)
    limit = 8047 * 1.2
    inner = {f"{p.lat:.6f},{p.lng:.6f}" for p in points if distance_meters(ORIGIN, p) <= limit / 2}
    maps = NearestFirstMaps(points)
    result = await SmartService(b"test", "prices_only", maps_web=maps).search(search(20))
    assert len(maps.queries) == result.upstream_calls["google_maps_web_search"] == 20
    found = {row.place_id for row in result.snapshot.inventory}
    # The previous five overlapping viewports found about a third of this inner area.
    assert len(found & inner) / len(inner) >= 0.7
    covered = result.snapshot.discovery_area_covered
    assert 0 < covered < 1
    assert any("Maps discovery surveyed an estimated" in warning for warning in result.snapshot.warnings)


async def test_nearby_searches_share_cached_cell_requests():
    maps = NearestFirstMaps(field(400, 6000))
    service = SmartService(b"test", "prices_only", maps_web=maps)
    await service.search(search(12))
    first = len(maps.queries)
    moved = Point(lat=ORIGIN.lat + 0.002, lng=ORIGIN.lng)  # ~220m away
    second = await service.search(search(12, moved))
    assert second.cache_hits >= 3
    assert len(maps.queries) - first < 12


def test_primary_h3_viewport_is_stable_for_nearby_points_and_covers_cell_boundary():
    import h3

    from gaswise.services.pricing.discovery import shared_viewport
    centre,radius = shared_viewport(ORIGIN,6000)
    moved = Point(lat=ORIGIN.lat+.00001,lng=ORIGIN.lng+.00001)
    assert shared_viewport(moved,6000) == (centre,radius)
    cell = h3.latlng_to_cell(ORIGIN.lat,ORIGIN.lng,8)
    assert all(distance_meters(centre,Point(lat=lat,lng=lng))+6000 <= radius for lat,lng in h3.cell_to_boundary(cell))
