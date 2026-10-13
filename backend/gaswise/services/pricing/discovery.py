"""Independent price acquisition, bounded globally by SmartService cache loaders."""
import asyncio
import math

import h3

from gaswise.contracts.common import Point
from gaswise.contracts.sources import MAPS_WEB_PAGE_SIZE, GasBuddySearch, GooglePriceSearch, MapsWebSearch
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.cells import Coverage
from gaswise.domain.pricing.comparison import search_limit_meters


def shared_viewport(point, radius):
    """Stable geographic query cells; enlarge viewport, then filter the true circle.

    This is cache reuse, not a ZIP polygon or a claim of exhaustive inventory.
    Route endpoints and station coordinates are never snapped.
    """
    if radius > 45000 or abs(point.lat) > 84:
        return point, radius
    cell = h3.latlng_to_cell(point.lat, point.lng, 8)
    latitude, longitude = h3.cell_to_latlng(cell)
    centre = Point(lat=latitude, lng=longitude)
    # Fixed for the whole cell, including points near its boundary; never use caller offset in the key.
    from gaswise.domain.pricing.comparison import distance_meters
    margin = max(distance_meters(centre, Point(lat=lat,lng=lng)) for lat,lng in h3.cell_to_boundary(cell))
    shared_radius = math.ceil(radius / 500) * 500 + math.ceil(margin / 100) * 100
    return centre, min(50000, shared_radius)


MAPS_WAVE = 6
MAPS_CACHE_SECONDS = 300


async def discover_maps(service, search, query):
    """One whole-area request, then waves of nearest unproven points within the request budget.

    Waves shrink the query radius wherever a page fills up inside it, so dense blocks
    are read with small viewports and sparse ones stay a single request.
    """
    limit = search_limit_meters(search)
    coverage = Coverage(search.origin, limit)
    outcomes = []
    # The snapped whole-area request is shared by nearby users and ends sparse searches.
    batch = [shared_viewport(search.origin, limit)]
    while batch:
        tiles = [
            MapsWebSearch(origin=point, fuel_type=search.fuel_type, radius_meters=radius, max_results=100,
                          detail_limit=query.maps_detail_limit if not outcomes and index == 0 else 0)
            for index, (point, radius) in enumerate(batch)
        ]
        results = await asyncio.gather(*(
            service.cached("maps:" + tile.model_dump_json(), lambda tile=tile: service.maps_web.prices(tile),
                           seconds=MAPS_CACHE_SECONDS, refresh=query.force_refresh)
            for tile in tiles
        ), return_exceptions=True)
        rate_limited = False
        for tile, result in zip(tiles, results, strict=True):
            if isinstance(result, BaseException) and not isinstance(result, ProviderError):
                raise result
            outcomes.append(result)
            if isinstance(result, ProviderError):
                rate_limited = rate_limited or "rate_limit" in str(result)
                continue
            value, _ = result
            coverage.record(tile.origin, tile.radius_meters, value.candidate_count, len(value.inventory),
                            value.candidate_reach_meters, MAPS_WEB_PAGE_SIZE)
        remaining = query.discovery_tiles - len(outcomes)
        if rate_limited or remaining <= 0:
            break
        points, radius = coverage.wave(min(MAPS_WAVE, remaining))
        batch = [(point, radius) for point in points]
    return outcomes, coverage.fraction()


async def acquire(service, search, query):
    requests = {}
    if service.gasbuddy is not None:
        # Coordinates, not ZIP: a ZIP search stops at the ZIP line. The snapped centre lets
        # nearby users share one cached GasBuddy request with a fixed enlarged radius.
        limit = search_limit_meters(search)
        centre, shared_radius = shared_viewport(search.origin, limit)
        gb = GasBuddySearch(max_pages=query.gasbuddy_page_limit, origin=centre,
                            radius_meters=min(60000, shared_radius),
                            fuel_type=search.fuel_type, payment_type="cash_or_credit",
                            include_payment_variants=True, max_results=100)
        requests["gasbuddy"] = service.cached("gasbuddy:" + gb.model_dump_json(), lambda: service.gasbuddy.prices(gb), refresh=query.force_refresh)
    if service.maps_web is not None:
        requests["maps"] = discover_maps(service, search, query)
    if service.waze is not None:
        centre, radius = shared_viewport(search.origin, search_limit_meters(search))
        waze = GooglePriceSearch(origin=centre, fuel_type=search.fuel_type, radius_meters=min(50000, radius), max_results=20)
        requests["waze"] = service.cached("waze:" + waze.model_dump_json(), lambda: service.waze.stations(waze), refresh=query.force_refresh)
    # Per-source failures stay isolated; cancellation still propagates to all waiters.
    values = await asyncio.gather(*requests.values(), return_exceptions=True)
    return dict(zip(requests, values, strict=True))


def acquired(values, key):
    value = values[key]
    if isinstance(value, BaseException):
        raise value
    return value
