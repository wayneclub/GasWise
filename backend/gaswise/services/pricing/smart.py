"""Bounded cached acquisition and signed client-held snapshots; no persistent history."""

import asyncio
import copy
import hashlib
import hmac
import json
import math
import secrets
from datetime import UTC, datetime, timedelta
from time import monotonic, perf_counter

from gaswise.contracts.common import Point, Route, SourceStatus, Station
from gaswise.contracts.search import Search
from gaswise.contracts.smart import ProgressiveSearchState, SmartResult, SmartSearch, SmartSnapshot, SnapshotRoute
from gaswise.contracts.sources import GooglePriceSearch, MapsWebSearch
from gaswise.domain.ports import PriceSnapshot, ProviderError
from gaswise.domain.pricing.comparison import (
    comparison_price,
    distance_meters,
    ineligible,
    merged_opening,
    search_limit_meters,
    select_prices,
)
from gaswise.domain.pricing.identity import inventory_match, located_inventory_match, site_match
from gaswise.domain.pricing.payment import snapshot_history
from gaswise.domain.pricing.route_estimates import estimate_route
from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.domain.pricing.top_tier import tag_top_tier
from gaswise.domain.vehicles.fuel_policy import check_vehicle_fuel, resolve_fuel_query
from gaswise.services.pricing.cache import TTLCache
from gaswise.services.pricing.discovery import acquire, acquired
from gaswise.services.pricing.regional import address_region, benchmarks, match_benchmark
from gaswise.services.pricing.search import SearchService
from gaswise.services.pricing.shared_cache import cache_observations


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


def gasbuddy_station(quote, matched=None):
    """GasBuddy's own coordinates place a quote; a matched Google place adds identity and ratings."""
    common = dict(
        id=quote.id,
        name=quote.name,
        address=quote.address,
        price_per_gallon=quote.price_per_gallon,
        fuel_type=quote.fuel_type,
        payment_type=quote.payment_type,
        price_updated_at=quote.price_updated_at,
        fetched_at=quote.fetched_at,
        source="gasbuddy_web",
        membership_required=quote.membership_required,
    )
    if matched is None:
        return Station(
            **common,
            canonical_id=f"gasbuddy:{quote.id}",
            location=quote.location,
            attribution=["GasBuddy"],
            details={"source_url": quote.source_url, "location_source": "gasbuddy_web"},
        )
    return Station(
        **common,
        canonical_id=f"google_places:{matched.place_id}",
        location=matched.location,
        attribution=["GasBuddy", "Google Maps"],
        rating=matched.rating,
        review_count=matched.review_count,
        rating_source=matched.rating_source,
        details={
            "opening_status": matched.opening_status,
            "source_url": quote.source_url,
            "location_source_name": matched.name,
            "location_source": "google_maps_web",
        },
        **merged_opening(matched),
    )


class SnapshotProvider:
    def __init__(self, snapshot):
        self.data = snapshot
        self.candidate_limit = 1000 if snapshot.estimate_unrouted_routes else 30

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
        if self.data.estimate_unrouted_routes and via is not None and self.data.baseline is not None:
            return estimate_route(origin, destination, via, self.data.baseline)
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
        aaa=None,
        shared_cache=None,
    ):
        self.secret, self.mode = secret, mode
        self.gasbuddy, self.google, self.router, self.demo = gasbuddy, google, router, demo
        self.waze = waze
        self.maps_web = maps_web
        self.vehicles = vehicles
        self.top_tier = top_tier
        self.aaa = aaa
        self.shared_cache = shared_cache
        self.hot_refresh = None
        self.base_collection = None
        self.inflight = {}
        self.waiters = {}
        # Maps discovery runs one whole-area request and then waves of nearest
        # unproven points. Measured production first searches spent ~4.5s in four
        # sequential six-wide waves; the wave width and slot count must agree or
        # the extra tiles simply queue. Per-source minute budgets still apply.
        self.source_slots = {"gasbuddy": asyncio.Semaphore(1), "maps": asyncio.Semaphore(8), "waze": asyncio.Semaphore(2), "aaa": asyncio.Semaphore(1)}
        self.background_gasbuddy_slot = asyncio.Semaphore(1)
        # Each station route is two dependent website requests. A live 20-route
        # search took ~5.3s at four slots; eight keeps the same bounded shortlist
        # but halves the number of waves. Routes are cached for 300s.
        self.route_slots = asyncio.Semaphore(8)
        self.cache = TTLCache()
        self.failures = TTLCache(capacity=64)
        self.source_failures = TTLCache(capacity=16)
        self.progressive_jobs = {}
        self.progressive_tasks = set()
        self.progressive_slots = asyncio.Semaphore(8)

    def sign(self, snapshot):
        # Clients return the snapshot through their own JSON stack, so sign a canonical form.
        return hmac.new(self.secret, snapshot_bytes(snapshot), hashlib.sha256).hexdigest()

    async def search(self, query):
        return await self.coalesce("search:" + query.model_dump_json(), lambda: self.collect(query))

    def _progressive_state(self, job):
        return ProgressiveSearchState(**{key: value for key, value in job.items() if key != "updated_at"})

    def _prune_progressive_jobs(self):
        cutoff = monotonic() - 300
        for job_id in [key for key, job in self.progressive_jobs.items() if job["updated_at"] < cutoff]:
            self.progressive_jobs.pop(job_id, None)

    async def start_progressive_search(self, query):
        self._prune_progressive_jobs()
        active = sum(job["status"] in {"pending", "partial"} for job in self.progressive_jobs.values())
        if active >= 8:
            raise ProviderError("progressive_search_capacity_exceeded")
        if len(self.progressive_jobs) >= 100:
            terminal = next(
                (key for key, job in self.progressive_jobs.items() if job["status"] in {"complete", "failed"}),
                None,
            )
            if terminal is not None:
                self.progressive_jobs.pop(terminal)
        job_id = secrets.token_urlsafe(24)
        job = {
            "job_id": job_id,
            "status": "pending",
            "revision": 0,
            "completed_sources": [],
            "result": None,
            "error": None,
            "updated_at": monotonic(),
        }
        self.progressive_jobs[job_id] = job
        task = asyncio.create_task(self._run_progressive_search(job, query))
        self.progressive_tasks.add(task)
        task.add_done_callback(self.progressive_tasks.discard)
        return self._progressive_state(job)

    async def poll_progressive_search(self, job_id):
        self._prune_progressive_jobs()
        job = self.progressive_jobs.get(job_id)
        return self._progressive_state(job) if job is not None else None

    async def _run_progressive_search(self, job, query):
        try:
            async with self.progressive_slots:
                if self.demo is not None:
                    result = await self.search(query)
                    job.update(status="complete", revision=1, completed_sources=["synthetic"], result=result, updated_at=monotonic())
                    return
                sources = [name for name, provider in (("gasbuddy", self.gasbuddy), ("maps", self.maps_web), ("waze", self.waze)) if provider is not None]
                source_query = query

                async def collect_source(source):
                    try:
                        return source, await self.collect(source_query, sources={source})
                    except ProviderError:
                        return source, None

                tasks = [asyncio.create_task(collect_source(source)) for source in sources]
                results = []
                try:
                    for completed in asyncio.as_completed(tasks):
                        source, result = await completed
                        job["completed_sources"].append(source)
                        if result is not None:
                            results.append(result)
                            merged = await self._merge_progressive_results(results)
                            job.update(
                                status="partial" if len(job["completed_sources"]) < len(sources) else "complete",
                                revision=job["revision"] + 1,
                                result=merged,
                                updated_at=monotonic(),
                            )
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                if job["result"] is None:
                    job.update(status="failed", error="smart_price_sources_unavailable", updated_at=monotonic())
                elif len(job["completed_sources"]) == len(sources):
                    job.update(status="complete", updated_at=monotonic())
        except asyncio.CancelledError:
            raise
        except Exception:
            job.update(status="failed", error="progressive_search_failed", updated_at=monotonic())

    async def _merge_progressive_results(self, results):
        newest = results[-1]
        snapshot = newest.snapshot.model_copy(deep=True)
        stations = {}
        statuses = {}
        inventory = {}
        warnings = []
        unlocated = {}
        upstream_calls = {}
        cache_hits = 0
        for result in results:
            cache_hits += result.cache_hits
            for key, value in result.upstream_calls.items():
                upstream_calls[key] = upstream_calls.get(key, 0) + value
            for station in result.snapshot.stations:
                key = (station.source, station.id, station.payment_type, station.price_per_gallon)
                stations[key] = station
            for status in result.snapshot.source_statuses:
                statuses[status.source] = status
            for item in result.snapshot.inventory:
                inventory[item.place_id] = item
            for warning in result.snapshot.warnings:
                if warning not in warnings:
                    warnings.append(warning)
            for quote in result.snapshot.unlocated_gasbuddy:
                unlocated[quote.id] = quote
        snapshot = snapshot.model_copy(update={
            "stations": list(stations.values()),
            "source_statuses": list(statuses.values()),
            "inventory": list(inventory.values()),
            "warnings": warnings,
            "unlocated_gasbuddy": list(unlocated.values()),
        })
        ranking = await self.rank(snapshot, snapshot.query) if snapshot.baseline is not None else None
        return SmartResult(
            snapshot=snapshot,
            signature=self.sign(snapshot),
            ranking=ranking,
            cache_hits=cache_hits,
            upstream_calls=upstream_calls,
            timings_ms={"total": max(result.timings_ms.get("total", 0) for result in results)},
        )

    async def cached(self, key, operation, seconds=90, refresh=False):
        source = key.split(":", 1)[0]
        source_slot = self.source_slots.get(source)
        if self.shared_cache is not None and source in {"gasbuddy", "maps", "waze"}:
            # Forced refresh cannot bypass the cross-user freshness window or source budgets.
            async def shared_operation():
                slot = self.background_gasbuddy_slot if source == "gasbuddy" and background_acquisition.get() else source_slot
                async with slot:
                    return await operation()
            if self.hot_refresh is not None:
                await self.hot_refresh.observe(source, key, shared_operation)
            return await self.shared_cache.get(source, key, shared_operation)
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

        async def guarded_operation():
            failure = self.source_failures.get(source)
            if failure:
                error = ProviderError(failure)
                error.cache_hit = True
                raise error
            return await operation()

        async def load():
            try:
                if source_slot is None:
                    value = await guarded_operation()
                else:
                    async with source_slot:
                        value = await guarded_operation()
            except ProviderError as error:
                if "rate_limited" in str(error):
                    self.source_failures.put(source, str(error), 30)
                self.failures.put(key, str(error), 30)
                raise
            self.failures.entries.pop(key, None)
            self.cache.put(key, value, seconds)
            return value

        try:
            value = await self.coalesce(key, load)
        except ProviderError as error:
            owned = copy.copy(error)
            owned.cache_hit = shared or getattr(error, "cache_hit", False)
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
        progressive_tasks = list(self.progressive_tasks)
        for task in progressive_tasks:
            task.cancel()
        await asyncio.gather(*progressive_tasks, return_exceptions=True)
        self.progressive_tasks.clear()
        self.progressive_jobs.clear()
        if self.shared_cache is not None:
            await self.shared_cache.close()
        tasks = list(self.inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.inflight.clear()
        self.cache.clear()
        self.failures.clear()
        self.source_failures.clear()
        self.failures.clear()

    async def collect(self, query, vehicle_override=None, sources=None):
        token = cache_observations.set({})
        try:
            return await self._collect(query, vehicle_override, sources)
        finally:
            cache_observations.reset(token)

    async def _collect(self, query, vehicle_override=None, sources=None):
        started = perf_counter()
        stage_timings = {}
        if query.calculate_routes and self.router is None and self.demo is None:
            # Fail before collecting any price or Places data.
            raise ProviderError("smart_routing_not_configured")
        search = Search.model_validate(
            query.model_dump(exclude={"estimate_unrouted_routes", "calculate_routes", "route_limit", "maps_detail_limit", "discovery_tiles", "force_refresh", "gasbuddy_page_limit", "station_lookup_limit"})
        )
        vehicle = vehicle_override
        if search.vehicle_id is not None and vehicle is None:
            if self.vehicles is None:
                raise ProviderError("vehicle_catalog_not_configured")
            vehicle = await self.vehicles.vehicle(search.vehicle_id)
        search = resolve_fuel_query(search, vehicle)
        if vehicle is not None:
            check_vehicle_fuel(vehicle, search)
        calls = {"gasbuddy_search": 0, "google_nearby": 0, "google_text_search": 0, "routes": 0}
        if vehicle is not None:
            calls["vehicle_catalog_lookup"] = int(vehicle_override is None)
        statuses, warnings, stations, unlocated = [], [], [], []
        if vehicle and vehicle.fuel_recommendation:
            warnings.extend(vehicle.fuel_recommendation.assessment_warnings)
        raw = None
        maps_inventory = []
        # Crosswalks use every discovered place; the snapshot keeps only the nearest ones.
        matching_inventory = []
        discovery_area_covered = None
        if self.demo is not None:
            stations = await self.demo.stations(search.model_copy(update={"max_results": 10}))
            statuses.append(SourceStatus(source="synthetic", status="ok", quote_count=len(stations)))
        else:
            acquisitions = await acquire(self, search, query, stage_timings, sources)
            if "gasbuddy" in acquisitions:
                try:
                    # Do not apply ranking choices at acquisition time.
                    raw, hit = acquired(acquisitions, "gasbuddy")
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
            if "maps" in acquisitions:
                # Explicit session source replaces paid Nearby discovery. Never
                # fall back to paid Places calls after a website failure.
                calls["google_maps_web_search"] = 0
                calls["google_maps_web_details"] = 0
                try:
                    # Each website response is one bounded page; discovery reports how much
                    # of the area those pages proved complete, never claims exhaustiveness.
                    outcomes, discovery_area_covered = acquired(acquisitions, "maps")
                    inventory_by_id, quotes_by_id = {}, {}
                    detail_requests = 0
                    for index, outcome in enumerate(outcomes):
                        if isinstance(outcome, ProviderError):
                            error = outcome
                            calls["google_maps_web_search"] += int(not getattr(error, "cache_hit", False))
                            calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(getattr(error, "cache_hit", False))
                            warnings.append(f"Discovery stopped for viewport {index + 1}: {error}")
                            continue
                        tile, hit = outcome
                        calls["google_maps_web_search"] += int(not hit)
                        calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                        detail_requests += tile.detail_requests if not hit else 0
                        for item in tile.inventory:
                            if distance_meters(search.origin, item.location) <= search_limit_meters(search):
                                old = inventory_by_id.get(item.place_id)
                                inventory_by_id[item.place_id] = item.model_copy(update=merged_opening(old, item)) if old else item
                        for item in tile.stations:
                            if distance_meters(search.origin, item.location) <= search_limit_meters(search):
                                key = (item.source, item.id, item.payment_type)
                                old = quotes_by_id.get(key)
                                quotes_by_id[key] = item.model_copy(update=merged_opening(old, item)) if old else item
                    if not inventory_by_id and not any(not isinstance(outcome, BaseException) for outcome in outcomes):
                        raise ProviderError("google_maps_web_discovery_unavailable")
                    if discovery_area_covered < 0.995:
                        warnings.append(
                            f"Maps discovery proved {discovery_area_covered:.0%} of the search area within its "
                            "request budget; stations farther out may be missing."
                        )
                    # A small, explicit address lookup budget recovers stations omitted
                    # from generic Maps viewports. Require the same full US address.
                    calls["google_maps_web_station_lookup"] = 0
                    if raw is not None and query.station_lookup_limit:
                        known_zips = {item.address.rsplit(" ", 1)[-1][:5] for item in inventory_by_id.values() if item.address}
                        candidates = {}
                        for quote in raw.prices:
                            age = (datetime.now(UTC) - quote.price_updated_at).total_seconds() / 60 if quote.price_updated_at else None
                            if quote.location is not None or age is None or age < -5 or age > search.max_price_age_minutes or inventory_match(list(inventory_by_id.values()), quote.address):
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
                        "inventory": sorted(inventory_by_id.values(), key=lambda item: distance_meters(search.origin, item.location))[:250],
                        "stations": list(quotes_by_id.values()),
                        "detail_requests": detail_requests,
                    })
                    maps_inventory = data.inventory
                    matching_inventory = list(inventory_by_id.values())
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
                    saved_mappings = await self.shared_cache.mappings("gasbuddy_web", [q.id for q in raw.prices]) if self.shared_cache else {}
                    mapped_inventory = {f"google_places:{row.place_id}": row for row in matching_inventory}
                    for quote in raw.prices:
                        matched = mapped_inventory.get(saved_mappings.get(quote.id))
                        # Revalidate a persisted link against current provider coordinates.
                        if matched is not None and (quote.location is None or distance_meters(quote.location, matched.location) > 75):
                            matched = None
                        if matched is None:
                            matched = site_match(matching_inventory, quote)
                        if matched is None and quote.location is None:
                            unlocated.append(quote)
                            continue
                        stations.append(gasbuddy_station(quote, matched))
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
            elif self.google is not None and sources is None:
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
                            if quote.location is not None:
                                stations.append(gasbuddy_station(quote))
                            else:
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
                                details=self.google.opening_details(place),
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
                located = [gasbuddy_station(quote) for quote in raw.prices if quote.location is not None]
                unlocated = [quote for quote in raw.prices if quote.location is None]
                stations.extend(located)
                statuses.append(SourceStatus(source="gasbuddy_web", status="ok", quote_count=len(located)))
                if unlocated:
                    warnings.append(
                        "Some GasBuddy quotes have no coordinates; their location and cost ranking are unavailable."
                    )
            if "waze" in acquisitions:
                calls["waze_search"] = 0
                try:
                    quotes, hit = acquired(acquisitions, "waze")
                    calls["waze_search"] += int(not hit)
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                    gasbuddy_sites = [s for s in stations if (s.canonical_id or "").startswith("gasbuddy:")]
                    for quote in quotes:
                        quote = quote.model_copy(update={"details": {**quote.details, "location_source": "waze"}})
                        matched = located_inventory_match(matching_inventory, quote)
                        if matched is None and (site := site_match(gasbuddy_sites, quote)) is not None:
                            quote = quote.model_copy(update={"canonical_id": site.canonical_id})
                        if matched is not None:
                            quote = quote.model_copy(
                                update={
                                    "canonical_id": f"google_places:{matched.place_id}",
                                    "location": matched.location,
                                    **merged_opening(quote, matched),
                                    "details": {**quote.details, "regional_address": matched.address, "location_source": "google_maps_web"},
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
            if sources is None and not any(s.status == "ok" for s in statuses):
                # Preserve the actionable deferral code when every configured source
                # failed because no verified US pricing lane was available.
                if statuses and all(s.detail == "pricing_egress_unavailable" for s in statuses):
                    raise ProviderError("pricing_egress_unavailable")
                raise ProviderError("smart_price_sources_unavailable")
        if self.top_tier is not None:
            # Tagged once at acquisition and signed with the snapshot; reranks reuse the tags.
            stations = tag_top_tier(stations, self.top_tier.index)
        if self.shared_cache is not None:
            await self.shared_cache.observe(stations)
            if hasattr(self.shared_cache, "payment_history"):
                try:
                    history = await self.shared_cache.payment_history(stations)
                    stations = [s.model_copy(update={"payment_history": snapshot_history(s, history.get(s.canonical_id, [])) if s.payment_type == "unknown" else []}) for s in stations]
                except ProviderError:
                    warnings.append("Station payment history unavailable; no history estimate used.")
        now = datetime.now(UTC)
        snapshot = SmartSnapshot(
            query=search,
            estimate_unrouted_routes=query.estimate_unrouted_routes,
            acquisition_options={key: getattr(query, key) for key in ("gasbuddy_page_limit", "discovery_tiles", "maps_detail_limit", "station_lookup_limit")},
            stations=stations,
            source_statuses=statuses,
            source_cache=cache_observations.get() or {},
            collected_at=now,
            expires_at=now + timedelta(minutes=10),
            warnings=warnings,
            unlocated_gasbuddy=unlocated[:100],
            discovery_area_covered=discovery_area_covered,
            inventory=maps_inventory,
            vehicle=vehicle,
        )
        async def averages():
            if self.aaa is None:
                return
            states = sorted({state for st in stations if (state := address_region(st.address)[1])})[:3]
            for state in states:
                try:
                    data, hit = await self.cached("aaa:" + state, lambda: self.aaa.averages(state), seconds=21600)
                    calls["aaa_averages"] = calls.get("aaa_averages", 0) + int(not hit)
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                    snapshot.regional_averages.extend(benchmarks(data, search.fuel_type))
                except ProviderError as error:
                    hit = getattr(error, "cache_hit", False)
                    calls["aaa_averages"] = calls.get("aaa_averages", 0) + int(not hit)
                    calls["_cache_hits"] = calls.get("_cache_hits", 0) + int(hit)
                    snapshot.warnings.append("AAA regional average unavailable for " + state)

        discovery_done = perf_counter()

        async def timed(name, operation):
            started = perf_counter()
            try:
                await operation
            finally:
                stage_timings[name] = round((perf_counter() - started) * 1000, 1)

        if query.calculate_routes:
            await asyncio.gather(
                timed("routes", self.collect_routes(snapshot, min(query.route_limit, 20) if query.estimate_unrouted_routes else query.route_limit, calls)),
                timed("aaa_averages", averages()),
            )
        else:
            await timed("aaa_averages", averages())
        routes_done = perf_counter()
        signature = self.sign(snapshot)
        ranking = await self.rank(snapshot, search) if query.calculate_routes else None
        timings_ms = {
            "discovery": round((discovery_done - started) * 1000, 1),
            "routes_and_averages": round((routes_done - discovery_done) * 1000, 1),
            "ranking": round((perf_counter() - routes_done) * 1000, 1),
            **stage_timings,
            "total": round((perf_counter() - started) * 1000, 1),
        }
        return SmartResult(snapshot=snapshot, signature=signature, ranking=ranking, cache_hits=calls.pop("_cache_hits", 0), upstream_calls=calls, timings_ms=timings_ms)

    async def collect_routes(self, snapshot, route_limit, calls):
        search = snapshot.query
        now = datetime.now(UTC)
        snapshot.routes_checked_at = snapshot.routes_checked_at or now
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
        selections, _, _ = select_prices(
            snapshot.stations,
            search if snapshot.estimate_unrouted_routes else search.model_copy(update={"payment_type": "cash_or_credit"}),
            now,
        )
        unique = {point_key(row.station.location): row.station for row in selections}
        if snapshot.estimate_unrouted_routes:
            estimated = await SearchService(
                SnapshotProvider(snapshot), self.mode, vehicle_profile=snapshot.vehicle
            ).search(search.model_copy(update={"max_results": 100}))
            ordered = {point_key(row.station.location): row.station for row in estimated.results}
            # Keep every point for explicit expansion even beyond the displayed top 100.
            by_price = [*ordered.values(), *(st for key, st in unique.items() if key not in ordered)]
        else:
            by_price = sorted(unique.values(), key=comparison_price)
        by_distance = sorted(unique.values(), key=lambda st: distance_meters(search.origin, st.location))
        chosen = {}
        for cheap, near in zip(by_price, by_distance, strict=True):
            for st in (near, cheap):
                if len(chosen) < route_limit:
                    chosen.setdefault(point_key(st.location), st)
        existing = {point_key(row.via) for row in snapshot.routes}
        pending = [st for st in chosen.values() if point_key(st.location) not in existing]
        pending = pending[:max(0, route_limit - len(snapshot.routes))]

        async def bounded_route(st):
            async with self.route_slots:
                calls["routes"] += int(self.demo is None)
                try:
                    return SnapshotRoute(via=st.location, route=await fetch_route(st.location))
                except ProviderError:
                    snapshot.warnings.append(f"Route unavailable for {st.id}; no automatic retry.")
                    return None

        # Bound upstream concurrency across users, preserve deterministic input order.
        routed = await asyncio.gather(*(bounded_route(st) for st in pending))
        snapshot.routes.extend(row for row in routed if row is not None)
        if len(snapshot.routes) < len(unique):
            snapshot.warnings.append(
                "Unrouted stations use straight-line distance with a 1.3 road factor and 25 mph; traffic, road barriers and queues are not measured."
                if snapshot.estimate_unrouted_routes else "Some eligible stations lack routes; ranking coverage is partial."
            )

    def verify(self, snapshot, signature):
        if not hmac.compare_digest(signature, self.sign(snapshot)):
            raise ProviderError("invalid_snapshot_signature")
        if datetime.now(UTC) >= snapshot.expires_at:
            raise ProviderError("snapshot_expired")

    async def refresh_prices(self, request):
        return await self.coalesce("refresh-prices:" + request.model_dump_json(), lambda: self._refresh_prices(request))

    async def _refresh_prices(self, request):
        previous = request.snapshot
        self.verify(previous, request.signature)
        values = previous.query.model_dump()
        if request.options is not None:
            values.update(request.options.model_dump(exclude_unset=True))
        values.update(previous.acquisition_options)
        values.update(calculate_routes=False, estimate_unrouted_routes=previous.estimate_unrouted_routes)
        # The signed vehicle configuration and precise trip stay fixed during price refresh.
        fresh = await self.collect(SmartSearch.model_validate(values), previous.vehicle)
        snapshot = fresh.snapshot
        checked = previous.routes_checked_at or previous.collected_at
        snapshot.routes_checked_at = checked
        snapshot.baseline = previous.baseline.model_copy(deep=True) if previous.baseline else None
        snapshot.routes = [row.model_copy(deep=True) for row in previous.routes]
        if previous.baseline is not None:
            if (datetime.now(UTC) - checked).total_seconds() >= 900:
                snapshot.baseline, snapshot.routes = None, []
                snapshot.routes_checked_at = None
                try:
                    await self.collect_routes(snapshot, 20, fresh.upstream_calls)
                except ProviderError:
                    snapshot.baseline = previous.baseline.model_copy(deep=True)
                    snapshot.estimate_unrouted_routes = True
                    snapshot.warnings.append("Route refresh deferred; the older direct-trip baseline is retained and station detours are estimated.")
            else:
                snapshot.warnings.append("Existing routes were retained during price refresh; traffic was not refreshed.")
            fresh.ranking = await self.rank(snapshot, snapshot.query)
        fresh.signature = self.sign(snapshot)
        return fresh

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
        for row in [*result.results, *(row for board in result.leaderboards.values() for row in board)]:
            row.regional_benchmark = match_benchmark(row.station, snapshot.regional_averages)
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
