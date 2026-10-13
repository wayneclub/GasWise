"""Independent price acquisition, bounded globally by SmartService cache loaders."""
import asyncio
import math

from gaswise.contracts.common import Point
from gaswise.contracts.sources import GasBuddySearch, GooglePriceSearch, MapsWebSearch
from gaswise.domain.pricing.comparison import distance_meters as distance
from gaswise.domain.pricing.comparison import search_limit_meters


def shared_viewport(point, radius):
    """Stable geographic query cells; enlarge viewport, then filter the true circle.

    This is cache reuse, not a ZIP polygon or a claim of exhaustive inventory.
    Route endpoints and station coordinates are never snapped.
    """
    if radius > 45000 or abs(point.lat) > 84:
        return point, radius
    latitude_step = radius * 0.1 / 111320
    latitude = round(point.lat / latitude_step) * latitude_step
    longitude_step = latitude_step / max(0.1, math.cos(math.radians(latitude)))
    longitude = ((round(point.lng / longitude_step) * longitude_step + 180) % 360) - 180
    return Point(lat=latitude, lng=longitude), radius * 1.1


def tile_queries(search, query):
    offsets = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)][:query.discovery_tiles]
    offset = search.radius_meters * 0.45
    tiles = []
    for index, (north, east) in enumerate(offsets):
        point = Point(lat=max(-89, min(89, search.origin.lat + north * offset / 111320)),
                      lng=((search.origin.lng + east * offset / (111320 * max(0.1, math.cos(math.radians(search.origin.lat)))) + 180) % 360) - 180)
        centre, radius = shared_viewport(point, search_limit_meters(search))
        tiles.append(MapsWebSearch(origin=centre, fuel_type=search.fuel_type,
                                   radius_meters=radius, max_results=100,
                                   detail_limit=query.maps_detail_limit if index == 0 else 0))
    return tiles



async def acquire(service, search, query):
    requests = {}
    if service.gasbuddy is not None:
        # Coordinates, not ZIP: a ZIP search stops at the ZIP line. The snapped centre lets
        # nearby users share one cached GasBuddy request; its offset widens the radius.
        limit = search_limit_meters(search)
        centre, _ = shared_viewport(search.origin, limit)
        gb = GasBuddySearch(max_pages=query.gasbuddy_page_limit, origin=centre,
                            radius_meters=min(60000, limit + distance(search.origin, centre)),
                            fuel_type=search.fuel_type, payment_type="cash_or_credit",
                            include_payment_variants=True, max_results=100)
        requests["gasbuddy"] = service.cached("gasbuddy:" + gb.model_dump_json(), lambda: service.gasbuddy.prices(gb), refresh=query.force_refresh)
    if service.maps_web is not None:
        for index, tile in enumerate(tile_queries(search, query)):
            requests[f"maps:{index}"] = service.cached("maps:" + tile.model_dump_json(), lambda tile=tile: service.maps_web.prices(tile), refresh=query.force_refresh)
    if service.waze is not None:
        waze = GooglePriceSearch(origin=search.origin, fuel_type=search.fuel_type, radius_meters=search_limit_meters(search), max_results=20)
        requests["waze"] = service.cached("waze:" + waze.model_dump_json(), lambda: service.waze.stations(waze), refresh=query.force_refresh)
    # Per-source failures stay isolated; cancellation still propagates to all waiters.
    values = await asyncio.gather(*requests.values(), return_exceptions=True)
    return dict(zip(requests, values, strict=True))


def acquired(values, key):
    value = values[key]
    if isinstance(value, BaseException):
        raise value
    return value
