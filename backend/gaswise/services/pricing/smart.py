"""Bounded cached acquisition and signed client-held snapshots; no persistent history."""

import asyncio
import copy
import hashlib
import hmac
import json
import math
from datetime import UTC, datetime, timedelta

from gaswise.contracts.common import Point, Route, SourceStatus, Station
from gaswise.contracts.search import Search
from gaswise.contracts.smart import SmartResult, SmartSnapshot, SnapshotRoute
from gaswise.contracts.sources import GasBuddySearch, GooglePriceSearch, MapsWebSearch
from gaswise.domain.ports import PriceSnapshot, ProviderError
from gaswise.domain.pricing.comparison import (
    comparison_price,
    distance_meters,
    ineligible,
    merged_opening,
    select_prices,
)
from gaswise.domain.pricing.identity import inventory_match
from gaswise.domain.pricing.top_tier import tag_top_tier
from gaswise.domain.vehicles.fuel_policy import check_vehicle_fuel, resolve_fuel_query
from gaswise.services.pricing.cache import TTLCache
from gaswise.services.pricing.search import SearchService


def canonical(value):
    """JSON-number-agnostic form: browsers re-serialize 3.0 as 3 and reorder integer-like keys."""
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return value


def snapshot_bytes(snapshot):
    payload = canonical(snapshot.model_dump(mode="json"))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def point_key(point):
    return point.lat, point.lng


class SnapshotProvider:
    def __init__(self, snapshot):
        self.data = snapshot

    async def snapshot(self, query):
        return PriceSnapshot(self.data.stations, self.data.source_statuses)

    async def stations(self, query):
        return (await self.snapshot(query)).stations

    async def route(self, origin, destination, via=None):
        if via is None and self.data.baseline is not None:
            return self.data.baseline
        for row in self.data.routes:
            if via is not None and point_key(row.via) == point_key(via):
                return row.route
        raise ProviderError("route_not_in_snapshot")


class SmartService:
    def __init__(
        self,
        secret,
        mode,
        gasbuddy=None,
        google=None,
        router=None,
        demo=None,
        waze=None,
        maps_web=None,
        vehicles=None,
        top_tier=None,
    ):
        self.secret, self.mode = secret, mode
        self.gasbuddy, self.google, self.router, self.demo = gasbuddy, google, router, demo
        self.waze = waze
        self.maps_web = maps_web
        self.vehicles = vehicles
        self.top_tier = top_tier
        self.inflight = {}
        self.waiters = {}
        self.cache = TTLCache()
        self.failures = TTLCache(capacity=64)

    def sign(self, snapshot):
        # Clients return the snapshot through their own JSON stack, so sign a canonical form.
        return hmac.new(self.secret, snapshot_bytes(snapshot), hashlib.sha256).hexdigest()

    async def search(self, query):
        return await self.coalesce("search:" + query.model_dump_json(), lambda: self.collect(query))

    async def cached(self, key, operation, seconds=90, refresh=False):
        # Keys are digests: exact origin/query identity without plaintext coordinates.
        key = "cache:" + hashlib.sha256(key.encode()).hexdigest()
        if not refresh:
            failure = self.failures.get(key)
            if failure is not None:
                error = ProviderError(failure)
                error.cache_hit, error.upstream_http_requests = True, 0
                raise error
            value = self.cache.get(key)
            if value is not None:
                return value, True
        shared = key in self.inflight

        async def load():
            try:
                value = await operation()
            except ProviderError as error:
                self.failures.put(key, str(error), 30)
                raise
            self.failures.entries.pop(key, None)
            self.cache.put(key, value, seconds)
            return value

        try:
            value = await self.coalesce(key, load)
        except ProviderError as error:
            owned = copy.copy(error)
            owned.cache_hit = shared
            if shared:
                owned.upstream_http_requests = 0
            raise owned from None
        return copy.deepcopy(value), shared

    async def coalesce(self, key, operation):
        # Merge concurrent clicks; no retained completed-response cache.
        task = self.inflight.get(key)
        if task is None:
            task = asyncio.create_task(operation())
            self.inflight[key] = task

            def cleanup(done):
                if self.inflight.get(key) is done:
                    self.inflight.pop(key, None)
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(cleanup)
        self.waiters[key] = self.waiters.get(key, 0) + 1
        try:
            return await asyncio.shield(task)
        finally:
            self.waiters[key] -= 1
            if self.waiters[key] == 0:
                self.waiters.pop(key)
                if not task.done():
                    task.cancel()
            if task.done() and self.inflight.get(key) is task:
                self.inflight.pop(key, None)

    async def close(self):
        tasks = list(self.inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.inflight.clear()
        self.cache.clear()
        self.failures.clear()

    async def collect(self, query):
        if query.calculate_routes and self.router is None and self.demo is None:
            # Fail before collecting any price or Places data.
            raise ProviderError("smart_routing_not_configured")
        search = Search.model_validate(
            query.model_dump(exclude={"calculate_routes", "route_limit", "maps_detail_limit", "discovery_tiles", "force_refresh", "gasbuddy_page_limit", "station_lookup_limit"})
        )
        vehicle = None
        if search.vehicle_id is not None:
            if self.vehicles is None:
                raise ProviderError("vehicle_catalog_not_configured")
            vehicle = await self.vehicles.vehicle(search.vehicle_id)
        search = resolve_fuel_query(search, vehicle)
        if vehicle is not None:
            check_vehicle_fuel(vehicle, search)
        calls = {"gasbuddy_search": 0, "google_nearby": 0, "google_text_search": 0, "routes": 0}
        if vehicle is not None:
            calls["vehicle_catalog_lookup"] = 1
        statuses, warnings, stations, unlocated = [], [], [], []
        if vehicle and vehicle.fuel_recommendation:
            warnings.extend(vehicle.fuel_recommendation.assessment_warnings)
        raw = None
        maps_inventory = []
        if self.demo is not None:
            stations = await self.demo.stations(search.model_copy(update={"max_results": 10}))
            statuses.append(SourceStatus(source="synthetic", status="ok", quote_count=len(stations)))
        else:
            if self.gasbuddy is not None:
                try:
                    # Do not apply ranking choices at acquisition time.
                    gb_query = GasBuddySearch(
                            max_pages=query.gasbuddy_page_limit,
                            origin=search.origin,
                            postal_code=search.postal_code,
                            fuel_type=search.fuel_type,
                            payment_type="cash_or_credit",
                            include_payment_variants=True,
                            max_results=100,
                        )
                    raw, hit = await self.cached("gasbuddy:" + gb_query.model_dump_json(), lambda: self.gasbuddy.prices(gb_query), refresh=query.force_refresh)
                    calls["gasbuddy_search"] += int(not hit)
                    calls["gasbuddy_pages"] = raw.page_requests if not hit else 0
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                    warnings.extend(raw.warnings)
                except ProviderError as error:
                    calls["gasbuddy_search"] += int(not getattr(error, "cache_hit", False))
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(getattr(error, "cache_hit", False))
                    statuses.append(
                        SourceStatus(source="gasbuddy_web", status="unavailable", detail=str(error))
                    )
            if self.maps_web is not None:
                # Explicit session source replaces paid Nearby discovery. Never
                # fall back to paid Places calls after a website failure.
                calls["google_maps_web_search"] = 0
                calls["google_maps_web_details"] = 0
                try:
                    # Sample the centre and four overlapping viewports. Each website
                    # response is bounded; this improves coverage, not exhaustiveness.
                    offsets = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)][:query.discovery_tiles]
                    inventory_by_id, quotes_by_id = {}, {}
                    detail_requests = 0
                    for index, (north, east) in enumerate(offsets):
                        if index:
                            await asyncio.sleep(1)
                        offset = search.radius_meters * 0.45
                        centre = Point(
                            lat=max(-89, min(89, search.origin.lat + north * offset / 111320)),
                            lng=((search.origin.lng + east * offset / (111320 * max(0.1, math.cos(math.radians(search.origin.lat)))) + 180) % 360) - 180,
                        )
                        try:
                            tile_query = MapsWebSearch(
                                origin=centre, fuel_type=search.fuel_type,
                                radius_meters=search.radius_meters, max_results=100,
                                detail_limit=query.maps_detail_limit if index == 0 else 0,
                            )
                            tile, hit = await self.cached("maps:" + tile_query.model_dump_json(), lambda: self.maps_web.prices(tile_query), refresh=query.force_refresh)
                            calls["google_maps_web_search"] += int(not hit)
                            calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                        except ProviderError as error:
                            calls["google_maps_web_search"] += int(not getattr(error, "cache_hit", False))
                            calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(getattr(error, "cache_hit", False))
                            if not inventory_by_id:
                                raise
                            warnings.append(f"Discovery stopped after {index} completed viewports: {error}")
                            break
                        detail_requests += tile.detail_requests if not hit else 0
                        for item in tile.inventory:
                            if distance_meters(search.origin, item.location) <= search.radius_meters:
                                old = inventory_by_id.get(item.place_id)
                                inventory_by_id[item.place_id] = item.model_copy(update=merged_opening(old, item)) if old else item
                        for item in tile.stations:
                            if distance_meters(search.origin, item.location) <= search.radius_meters:
                                key = (item.source, item.id, item.payment_type)
                                old = quotes_by_id.get(key)
                                quotes_by_id[key] = item.model_copy(update=merged_opening(old, item)) if old else item
                    # A small, explicit address lookup budget recovers stations omitted
                    # from generic Maps viewports. Require the same full US address.
                    calls["google_maps_web_station_lookup"] = 0
                    if raw is not None and query.station_lookup_limit:
                        known_zips = {item.address.rsplit(" ", 1)[-1][:5] for item in inventory_by_id.values() if item.address}
                        candidates = {}
                        for quote in raw.prices:
                            age = (datetime.now(UTC) - quote.price_updated_at).total_seconds() / 60 if quote.price_updated_at else None
                            if age is None or age < -5 or age > search.max_price_age_minutes or inventory_match(list(inventory_by_id.values()), quote.address):
                                continue
                            candidates.setdefault(quote.address, quote)
                        candidates = sorted(candidates.values(), key=lambda q: (q.postal_code[:5] not in known_zips, q.price_per_gallon))
                        for quote in candidates[:query.station_lookup_limit]:
                            lookup = MapsWebSearch(origin=search.origin, fuel_type=search.fuel_type, radius_meters=search.radius_meters, max_results=10, search_text="gas station " + quote.address)
                            try:
                                located, hit = await self.cached("maps:" + lookup.model_dump_json(), lambda: self.maps_web.prices(lookup), seconds=90, refresh=query.force_refresh)
                                calls["google_maps_web_station_lookup"] += int(not hit)
                                calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                                matched = inventory_match(located.inventory, quote.address)
                                if matched is not None:
                                    inventory_by_id[matched.place_id] = matched
                                    for item in located.stations:
                                        if item.canonical_id == "google_places:" + matched.place_id:
                                            quotes_by_id[(item.source, item.id, item.payment_type)] = item
                            except ProviderError as error:
                                calls["google_maps_web_station_lookup"] += int(not getattr(error, "cache_hit", False))
                                calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(getattr(error, "cache_hit", False))
                                warnings.append("Station address lookup stopped: " + str(error))
                                break
                    data = tile.model_copy(update={
                        "inventory": sorted(inventory_by_id.values(), key=lambda item: distance_meters(search.origin, item.location))[:100],
                        "stations": list(quotes_by_id.values()),
                        "detail_requests": detail_requests,
                    })
                    maps_inventory = data.inventory
                    stations.extend(data.stations)
                    warnings.extend(data.warnings)
                    calls["google_maps_web_details"] = data.detail_requests
                    statuses.append(
                        SourceStatus(source="google_maps_web", status="ok", quote_count=len(data.stations))
                    )
                except ProviderError as error:
                    statuses.append(
                        SourceStatus(source="google_maps_web", status="unavailable", detail=str(error))
                    )
                if raw is not None:
                    for quote in raw.prices:
                        matched = inventory_match(maps_inventory, quote.address)
                        if matched is None:
                            unlocated.append(quote)
                            continue
                        stations.append(
                            Station(
                                id=quote.id,
                                canonical_id=f"google_places:{matched.place_id}",
                                name=quote.name,
                                location=matched.location,
                                address=quote.address,
                                price_per_gallon=quote.price_per_gallon,
                                fuel_type=quote.fuel_type,
                                payment_type=quote.payment_type,
                                price_updated_at=quote.price_updated_at,
                                fetched_at=quote.fetched_at,
                                source="gasbuddy_web",
                                membership_required=quote.membership_required,
                                attribution=["GasBuddy", "Google Maps"],
                                rating=matched.rating,
                                review_count=matched.review_count,
                                rating_source=matched.rating_source,
                                details={"opening_status": matched.opening_status, "source_url": quote.source_url, "location_source_name": matched.name},
                                **merged_opening(matched),
                            )
                        )
                    statuses.append(
                        SourceStatus(
                            source="gasbuddy_web",
                            status="ok",
                            quote_count=sum(s.source == "gasbuddy_web" for s in stations),
                        )
                    )
                    warnings.append(
                        f"{len(unlocated)} GasBuddy quotes lack an unambiguous inventory address match."
                    )
            elif self.google is not None:
                # Current GasBuddy contract has no verified coordinates: one nearby
                # inventory replaces N per-station Text Search calls. No extra price refresh.
                calls["google_nearby"] += 1
                google_error = None
                try:
                    data = await self.google.nearby_places(
                        GooglePriceSearch(
                            origin=search.origin,
                            fuel_type=search.fuel_type,
                            radius_meters=search.radius_meters,
                            max_results=20,
                        )
                    )
                    google_prices = self.google.prices_from_places(data, search)
                except ProviderError as error:
                    google_error = str(error)
                    data, google_prices = {"places": []}, []
                    warnings.append(
                        "Google unavailable; raw GasBuddy quotes remain available without guessed locations."
                    )
                if raw is not None:
                    for quote in raw.prices:
                        located = self.google.locate_from_places(data, quote)
                        if located is None:
                            unlocated.append(quote)
                            continue
                        place_id, point = located
                        place = next((p for p in data.get("places", []) if p.get("id") == place_id), {})
                        stations.append(
                            Station(
                                id=quote.id,
                                canonical_id=f"google_places:{place_id}",
                                name=quote.name,
                                location=Point(**point),
                                address=quote.address,
                                price_per_gallon=quote.price_per_gallon,
                                fuel_type=quote.fuel_type,
                                payment_type=quote.payment_type,
                                price_updated_at=quote.price_updated_at,
                                fetched_at=quote.fetched_at,
                                source="gasbuddy_web",
                                membership_required=quote.membership_required,
                                attribution=["GasBuddy", "Google Maps"],
                                rating=place.get("rating"),
                                review_count=place.get("userRatingCount"),
                                rating_source="Google Maps" if place.get("rating") is not None else None,
                                **self.google.opening(place),
                            )
                        )
                    statuses.append(
                        SourceStatus(source="gasbuddy_web", status="ok", quote_count=len(stations))
                    )
                    warnings.append(
                        f"{len(unlocated)} GasBuddy quotes could not be matched to this nearby inventory."
                    )
                # Prefer usable, dated GasBuddy prices. Google fills gaps only;
                # it is not unconditionally mixed into every station's evidence.
                usable = {
                    st.canonical_id
                    for st in stations
                    if ineligible(st, search, datetime.now(UTC)) is None and st.price_updated_at is not None
                }
                supplements = [st for st in google_prices if f"google_places:{st.id}" not in usable]
                stations.extend(supplements)
                statuses.append(
                    SourceStatus(
                        source="google_places",
                        status="unavailable" if google_error else "ok",
                        quote_count=len(supplements),
                        detail=google_error,
                    )
                )
            elif raw is not None:
                unlocated = raw.prices
                statuses.append(SourceStatus(source="gasbuddy_web", status="ok", quote_count=0))
                warnings.append(
                    "GasBuddy quotes have no verified coordinates; location and cost ranking unavailable."
                )
            if self.waze is not None:
                calls["waze_search"] = 0
                try:
                    waze_query = GooglePriceSearch(
                            origin=search.origin,
                            fuel_type=search.fuel_type,
                            radius_meters=search.radius_meters,
                            max_results=20,
                        )
                    quotes, hit = await self.cached("waze:" + waze_query.model_dump_json(), lambda: self.waze.stations(waze_query), refresh=query.force_refresh)
                    calls["waze_search"] += int(not hit)
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                    for quote in quotes:
                        matched = inventory_match(maps_inventory, quote.address, quote.location)
                        if matched is not None:
                            quote = quote.model_copy(
                                update={
                                    "canonical_id": f"google_places:{matched.place_id}",
                                    "location": matched.location,
                                    **merged_opening(quote, matched),
                                    "rating": matched.rating if matched.rating is not None else quote.rating,
                                    "review_count": matched.review_count if matched.rating is not None else quote.review_count,
                                    "rating_source": matched.rating_source if matched.rating is not None else quote.rating_source,
                                    "membership_required": quote.membership_required
                                    or next(
                                        (
                                            s.membership_required
                                            for s in stations
                                            if s.canonical_id == f"google_places:{matched.place_id}"
                                            and s.membership_required
                                        ),
                                        None,
                                    ),
                                }
                            )
                        stations.append(quote)
                    statuses.append(SourceStatus(source="waze", status="ok", quote_count=len(quotes)))
                    warnings.append("Waze payment conditions and numeric octane are unverified.")
                except ProviderError as error:
                    calls["waze_search"] += int(not getattr(error, "cache_hit", False))
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(getattr(error, "cache_hit", False))
                    statuses.append(SourceStatus(source="waze", status="unavailable", detail=str(error)))
            if not any(s.status == "ok" for s in statuses):
                raise ProviderError("smart_price_sources_unavailable")
        if self.top_tier is not None:
            # Tagged once at acquisition and signed with the snapshot; reranks reuse the tags.
            stations = tag_top_tier(stations, self.top_tier.index)
        now = datetime.now(UTC)
        snapshot = SmartSnapshot(
            query=search,
            stations=stations,
            source_statuses=statuses,
            collected_at=now,
            expires_at=now + timedelta(minutes=10),
            warnings=warnings,
            unlocated_gasbuddy=unlocated[:100],
            inventory=maps_inventory,
            vehicle=vehicle,
        )
        if query.calculate_routes:
            await self.collect_routes(snapshot, query.route_limit, calls)
        signature = self.sign(snapshot)
        ranking = await self.rank(snapshot, search) if query.calculate_routes else None
        return SmartResult(snapshot=snapshot, signature=signature, ranking=ranking, cache_hits=calls.pop("_cache_hits", 0), upstream_calls=calls)

    async def collect_routes(self, snapshot, route_limit, calls):
        search = snapshot.query
        now = datetime.now(UTC)
        router = self.demo or self.router
        counter_name = getattr(router, "http_counter_name", None)
        if counter_name:
            calls[counter_name] = 0
        destination = search.destination if search.trip_mode == "on_route" else search.origin

        async def fetch_route(via=None):
            try:
                route, hit = await self.cached(
                    "route:" + json.dumps([point_key(search.origin), point_key(destination), point_key(via) if via else None]),
                    lambda: router.route(search.origin, destination, via), seconds=300,
                )
                calls["routes"] -= int(hit and self.demo is None)
                calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
            except ProviderError as error:
                cached_failure = getattr(error, "cache_hit", False)
                calls["routes"] -= int(cached_failure and self.demo is None)
                calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(cached_failure)
                if counter_name:
                    calls[counter_name] += getattr(error, "upstream_http_requests", 0)
                raise
            if counter_name:
                calls[counter_name] += route.upstream_http_requests if not hit else 0
            return route

        if search.trip_mode == "on_route" and snapshot.baseline is None:
            calls["routes"] += int(self.demo is None)
            snapshot.baseline = await fetch_route()
        elif snapshot.baseline is None:
            snapshot.baseline = Route(distance_meters=0, duration_seconds=0, source="no_trip")
        # Keep cheap AND nearby candidates. This is bounded shortlist discovery,
        # not proof of a global optimum. All snapshot quotes remain available.
        selections, _, _ = select_prices(snapshot.stations, search.model_copy(update={"payment_type": "cash_or_credit"}), now)
        unique = {point_key(row.station.location): row.station for row in selections}
        by_price = sorted(unique.values(), key=comparison_price)
        by_distance = sorted(unique.values(), key=lambda st: distance_meters(search.origin, st.location))
        chosen = {}
        for cheap, near in zip(by_price, by_distance, strict=True):
            for st in (near, cheap):
                if len(chosen) < route_limit:
                    chosen.setdefault(point_key(st.location), st)
        existing = {point_key(row.via) for row in snapshot.routes}
        for st in chosen.values():
            if point_key(st.location) in existing or len(snapshot.routes) >= route_limit:
                continue
            calls["routes"] += int(self.demo is None)
            try:
                route = await fetch_route(st.location)
                snapshot.routes.append(SnapshotRoute(via=st.location, route=route))
            except ProviderError:
                snapshot.warnings.append(f"Route unavailable for {st.id}; no automatic retry.")
        if len(snapshot.routes) < len(unique):
            snapshot.warnings.append("Some eligible stations lack routes; ranking coverage is partial.")

    def verify(self, snapshot, signature):
        if not hmac.compare_digest(signature, self.sign(snapshot)):
            raise ProviderError("invalid_snapshot_signature")
        if datetime.now(UTC) >= snapshot.expires_at:
            raise ProviderError("snapshot_expired")

    async def add_routes(self, request):
        return await self.coalesce(
            "routes:" + request.model_dump_json(), lambda: self.route_snapshot(request)
        )

    async def route_snapshot(self, request):
        self.verify(request.snapshot, request.signature)
        if self.router is None and self.demo is None:
            raise ProviderError("smart_routing_not_configured")
        snapshot = request.snapshot.model_copy(deep=True)
        calls = {"gasbuddy_search": 0, "google_nearby": 0, "google_text_search": 0, "routes": 0}
        if snapshot.baseline is None or ("route_limit" in request.model_fields_set and len(snapshot.routes) < request.route_limit):
            await self.collect_routes(snapshot, request.route_limit, calls)
        return SmartResult(
            snapshot=snapshot,
            signature=self.sign(snapshot),
            ranking=await self.rank(snapshot, snapshot.query),
            cache_hits=calls.pop("_cache_hits", 0),
            upstream_calls=calls,
        )

    async def rank(self, snapshot, query):
        if snapshot.baseline is None:
            raise ProviderError("snapshot_has_no_routes")
        result = await SearchService(
            SnapshotProvider(snapshot), self.mode, vehicle_profile=snapshot.vehicle
        ).search(query)
        result.source_statuses = snapshot.source_statuses
        result.warnings.extend(snapshot.warnings)
        if query.payment_type != snapshot.query.payment_type:
            result.warnings.append(
                "Payment selection changed; only originally collected quotes are available."
            )
        result.generated_at = datetime.now(UTC)
        result.warnings.append(
            "Recalculated from the original snapshot; prices and traffic were not refreshed."
        )
        return result

    async def rerank(self, request):
        snapshot = request.snapshot
        self.verify(snapshot, request.signature)
        values = snapshot.query.model_dump()
        values.update(request.options.model_dump(exclude_unset=True))
        query = Search.model_validate(values)
        result = await self.rank(snapshot, query)
        snapshot = snapshot.model_copy(update={"query": query})
        calls = {"gasbuddy_search": 0, "google_nearby": 0, "google_text_search": 0, "routes": 0}
        if snapshot.vehicle is not None:
            calls["vehicle_catalog_lookup"] = 0
        return SmartResult(
            snapshot=snapshot, signature=self.sign(snapshot), ranking=result, upstream_calls=calls
        )
