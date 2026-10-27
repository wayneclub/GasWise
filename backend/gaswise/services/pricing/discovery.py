"""Independent price acquisition, bounded globally by SmartService cache loaders."""
import asyncio
import math
from time import perf_counter

import h3

from gaswise.contracts.common import Point
from gaswise.contracts.sources import (
    MAPS_WEB_PAGE_SIZE,
    GasBuddySearch,
    GooglePriceSearch,
    MapsWebSearch,
    MapsWebStation,
)
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.cells import Coverage
from gaswise.domain.pricing.comparison import distance_meters, search_limit_meters


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


# Live production probe: 6-wide waves needed five sequential rounds for the 20-request
# budget and proved 74% of an 8 km area; wider waves finished in fewer rounds and proved
# 84%. Eight keeps a bounded burst while removing the extra round trip.
MAPS_WAVE = 8
MAPS_CACHE_SECONDS = 300


async def discover_maps(service, search, query):
    """One whole-area request, then waves of nearest unproven points within the request budget.

    Waves shrink the query radius wherever a page fills up inside it, so dense blocks
    are read with small viewports and sparse ones stay a single request.
    """
    limit = search_limit_meters(search)
    coverage = Coverage(search.origin, limit)
    outcomes = []
    known = []
    if service.shared_cache is not None and hasattr(service.shared_cache, 'nearby_inventory'):
        known = await service.shared_cache.nearby_inventory(search.origin, limit)
    catalog = {row['canonical_id'].removeprefix('google_places:'): row for row in known
               if row['source'] == 'google_maps_web' and (row.get('canonical_id') or '').startswith('google_places:')}
    if hasattr(coverage, 'remember'):
        coverage.remember([dict(place_id=identifier, location=row['location']) for identifier, row in catalog.items()])
    seen = set()
    returned = 0
    # The snapped whole-area request is shared by nearby users and ends sparse searches.
    batch = [shared_viewport(search.origin, limit)]
    while batch:
        tiles = [
            MapsWebSearch(origin=point, fuel_type=search.fuel_type if not outcomes and query.maps_detail_limit else 'regular', radius_meters=radius, max_results=MAPS_WEB_PAGE_SIZE,
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
            value, hit = result
            # Every search response already carries all observed grades.
            if value.all_prices:
                value = value.model_copy(update={'stations': [row for row in value.all_prices if row.fuel_type == search.fuel_type]})
                outcomes[-1] = (value, hit)
            ids = {row.place_id for row in value.inventory if distance_meters(search.origin, row.location) <= limit}
            seen.update(ids)
            returned += len(ids)
            if hasattr(coverage, 'observed'):
                coverage.observed(ids)
            coverage.record(tile.origin, tile.radius_meters, value.candidate_count, len(value.inventory),
                            value.candidate_reach_meters, MAPS_WEB_PAGE_SIZE)
        remaining = query.discovery_tiles - len(outcomes)
        # Expanding the same failed source into more tiles amplifies outages
        # and expired-session failures. Keep earlier successful observations.
        failed_wave = all(isinstance(result, ProviderError) for result in results)
        if rate_limited or failed_wave or remaining <= 0:
            break
        points, radius = coverage.wave(min(MAPS_WAVE, remaining))
        batch = [(point, radius) for point in points]
    if outcomes and all(
        isinstance(item, ProviderError) and str(item) == "pricing_egress_unavailable"
        for item in outcomes
    ):
        # No verified US lane: surface the deferral itself instead of a generic
        # discovery failure so callers keep the actionable code.
        raise ProviderError("pricing_egress_unavailable")
    metrics = {'maps_observed_stations': len(seen), 'maps_known_stations': len(catalog),
               'maps_known_recovered': len(seen & catalog.keys()),
               'maps_known_missing': len(catalog.keys() - seen),
               'maps_duplicate_returns': returned - len(seen)}
    successes = [item for item in outcomes if not isinstance(item, BaseException)]
    if successes:
        target = successes[-1][0]
        target.discovery_metrics = metrics
        # Retain known stations without inventing a live observation or price.
        for identifier in sorted(catalog.keys() - seen):
            row = catalog[identifier]
            target.inventory.append(MapsWebStation(
                place_id=identifier, name=row['name'], address=row['address'], location=row['location'],
                distance_meters=distance_meters(search.origin, Point.model_validate(row['location'])),
                available_fuel_types=[], discovery_state='known', last_seen_at=row['last_seen_at']))
    return outcomes, coverage.fraction()


async def acquire(service, search, query, timings=None, sources=None):
    async def timed(name, operation):
        started = perf_counter()
        try:
            return await operation
        finally:
            if timings is not None:
                timings[name] = round((perf_counter() - started) * 1000, 1)

    requests = {}
    waze_metrics = {}
    if service.gasbuddy is not None and (sources is None or "gasbuddy" in sources):
        # Coordinates, not ZIP: a ZIP search stops at the ZIP line. The snapped centre lets
        # nearby users share one cached GasBuddy request with a fixed enlarged radius.
        limit = search_limit_meters(search)
        centre, shared_radius = shared_viewport(search.origin, limit)
        gb = GasBuddySearch(max_pages=query.gasbuddy_page_limit, origin=centre,
                            radius_meters=min(60000, shared_radius),
                            fuel_type=search.fuel_type, payment_type="cash_or_credit",
                            include_payment_variants=True, max_results=100)
        requests["gasbuddy"] = timed(
            "discovery_gasbuddy",
            service.cached("gasbuddy:" + gb.model_dump_json(), lambda: service.gasbuddy.prices(gb), refresh=query.force_refresh),
        )
    if service.maps_web is not None and (sources is None or "maps" in sources):
        requests["maps"] = timed("discovery_maps", discover_maps(service, search, query))
    if service.waze is not None and (sources is None or "waze" in sources):
        centre, radius = shared_viewport(search.origin, search_limit_meters(search))
        # Waze's wire request is independent of grade. Store all grades once,
        # using the same versioned namespace as fixed-base collection.
        waze = GooglePriceSearch(origin=centre, fuel_type="regular", radius_meters=min(50000, radius), max_results=20)

        async def waze_prices():
            known = []
            if service.shared_cache is not None and hasattr(service.shared_cache, 'nearby_inventory'):
                known = await service.shared_cache.nearby_inventory(search.origin, search_limit_meters(search))
            known = [row for row in known if row['source'] == 'waze']
            merged, seen, returned, loads, hits = {}, set(), 0, 0, 0

            async def fetch(tile):
                nonlocal returned, loads, hits
                rows, hit = await service.cached(
                    "waze:all-fuels-v1:" + tile.model_dump_json(),
                    lambda: service.waze.stations(tile, all_fuels=True), refresh=query.force_refresh)
                loads += int(not hit)
                hits += int(hit)
                ids = set()
                for row in rows:
                    if distance_meters(search.origin, row.location) > search_limit_meters(search):
                        continue
                    ids.add(row.id)
                    key = (row.id, row.fuel_type, row.payment_type)
                    old = merged.get(key)
                    if old is None or (row.price_updated_at or row.fetched_at) >= (old.price_updated_at or old.fetched_at):
                        merged[key] = row
                returned += len(ids)
                additional = len(ids - seen)
                seen.update(ids)
                return additional

            await fetch(waze)
            # Only known missing stations justify more Waze reads. Query whole
            # coarse cells, never one request per known station.
            cells = {}
            for row in known:
                if row['station_id'] not in seen:
                    point = Point.model_validate(row['location'])
                    cell = h3.latlng_to_cell(point.lat, point.lng, 7)
                    cells[cell] = cells.get(cell, 0) + 1
            attempts = 1
            for cell in sorted(cells, key=lambda cell: (-cells[cell], cell)):
                if attempts >= min(4, query.discovery_tiles):
                    break
                latitude, longitude = h3.cell_to_latlng(cell)
                point, local_radius = shared_viewport(Point(lat=latitude, lng=longitude), min(1600, radius))
                tile = waze.model_copy(update={'origin': point, 'radius_meters': local_radius})
                attempts += 1
                try:
                    if await fetch(tile) == 0:
                        break  # No marginal station yield; do not repeat overlapping reads.
                except ProviderError:
                    waze_metrics['waze_partial_failures'] = 1
                    break
            identifiers = {row['station_id'] for row in known}
            waze_metrics.update(waze_searches=loads, waze_cache_hits=hits,
                                waze_observed_stations=len(seen), waze_known_stations=len(identifiers),
                                waze_known_recovered=len(identifiers & seen),
                                waze_known_missing=len(identifiers - seen), waze_duplicate_returns=returned-len(seen))
            return [row for row in merged.values() if row.fuel_type == search.fuel_type], loads == 0
        requests["waze"] = timed(
            "discovery_waze",
            waze_prices(),
        )
    # Per-source failures stay isolated; cancellation still propagates to all waiters.
    values = await asyncio.gather(*requests.values(), return_exceptions=True)
    result = dict(zip(requests, values, strict=True))
    if waze_metrics:
        result['_waze_metrics'] = waze_metrics
    return result


def acquired(values, key):
    value = values[key]
    if isinstance(value, BaseException):
        raise value
    return value
