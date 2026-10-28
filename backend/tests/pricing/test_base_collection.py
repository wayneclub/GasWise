import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gaswise.contracts.sources import GasBuddySearch
from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.services.pricing.base_collection import BaseCollection, collection_jobs


class Cache:
    def __init__(self):
        self.jobs = {}
        self.saved = []
        self.used = 0
        self.fail = False

    async def _db(self, method, *args):
        if method == "configure_base_jobs":
            self.jobs = {job["id"]: job for job in args[0]}
        elif method == "claim_base_job":
            return next((key for key, job in self.jobs.items() if job["source"] in args[1]), None)
        elif method == "finish_base_job":
            self.saved.append(args)
            self.jobs.pop(args[0], None)
        elif method == "base_job_status":
            return list(self.jobs.values())
        elif method == "new_collection_canonical_count":
            return 1

    async def budget_state(self, source):
        return {"used": self.used, "background_day_used": 0}

    async def get(self, source, key, operation, *, wait_refresh=False):
        assert wait_refresh and background_acquisition.get()
        if self.fail:
            raise RuntimeError("provider rejected")
        return await operation(), False


class Provider:
    def __init__(self):
        self.calls = []

    async def prices(self, query):
        assert background_acquisition.get()
        self.calls.append(query)
        return SimpleNamespace(prices=[SimpleNamespace(
            id="station", source="gasbuddy_web", canonical_id=None,
            location=SimpleNamespace(lat=34.0, lng=-118.0), price_per_gallon=5,
        )])


def setup():
    cache, provider = Cache(), Provider()
    service = SimpleNamespace(shared_cache=cache, gasbuddy=provider, maps_web=None, waze=None,
                              background_gasbuddy_slot=asyncio.Semaphore(1), source_slots={})
    return BaseCollection(service, ["la", "irvine", "sd"]), cache, provider


async def test_fixed_bases_collect_without_any_foreground_uses_and_persist_due_jobs():
    collector, cache, provider = setup()
    await collector.initialize()
    assert len(cache.jobs) == 6
    assert {job["base"] for job in cache.jobs.values()} == {"la", "irvine", "sd"}
    while cache.jobs:
        assert await collector.step()
    assert len(provider.calls) == 6
    assert {query.fuel_type for query in provider.calls} == {"regular", "premium"}
    assert all(args[2:4] == (86400, None) for args in cache.saved)
    assert all(args[4:6] == (1, 1) for args in cache.saved)
    assert all(args[6]["canonical_count"] == 1 for args in cache.saved)
    assert all(args[6]["new_canonical_count"] == 1 for args in cache.saved)
    assert not background_acquisition.get()


async def test_busy_source_does_not_send_network_request_or_mark_success():
    collector, cache, provider = setup()
    await collector.initialize()
    cache.used = 6
    assert not await collector.step()
    assert provider.calls == []
    assert not cache.saved
    assert len(cache.jobs) == 6
    assert not background_acquisition.get()


async def test_failure_is_retryable_and_never_counts_as_success():
    collector, cache, provider = setup()
    await collector.initialize()
    cache.fail = True
    assert not await collector.step()
    assert cache.saved[0][2:4] == (3600, "collection_failed")
    assert not background_acquisition.get()


async def test_shutdown_cancellation_defers_job_for_prompt_retry_without_source_failure():
    # Deploys cancel the collector mid-job; that is an operator restart, not a provider failure.
    collector, cache, provider = setup()
    await collector.initialize()
    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError
    cache.get = cancel
    with pytest.raises(asyncio.CancelledError):
        await collector.step()
    assert cache.saved[0][2:4] == (60, "service_shutdown")
    assert not background_acquisition.get()


async def test_unexpected_base_exception_still_releases_job_as_interrupted():
    collector, cache, provider = setup()
    await collector.initialize()
    async def explode(*args, **kwargs):
        raise KeyboardInterrupt
    cache.get = explode
    with pytest.raises(KeyboardInterrupt):
        await collector.step()
    assert cache.saved[0][2:4] == (60, "interrupted")


def test_socal_catalog_covers_population_centers_and_corridor_supplements():
    from pydantic import ValidationError

    from gaswise.app.settings import Settings
    from gaswise.domain.pricing.collection_bases import BASE_CATALOG, BASES

    assert len(Settings(base_collection_preset="socal").base_collection_bases) == 85
    assert len(BASES) == 85
    assert len({base["census_geoid"] for base in BASE_CATALOG["bases"]}) == 85
    assert sum(base["selection_reason"] == "population_100000_plus" for base in BASE_CATALOG["bases"]) == 49
    assert {"la", "irvine", "sd", "industry", "rowland-heights", "barstow", "baker", "el-centro"} <= BASES.keys()
    assert all(32 < lat < 36 and -122 < lng < -114 for lat, lng in BASES.values())
    with pytest.raises(ValidationError):
        Settings(base_collection_bases=["unknown-city"])
    with pytest.raises(ValidationError):
        Settings(base_collection_bases=["la", "la"])


async def test_all_bases_have_jobs_even_without_foreground_requests():
    from gaswise.domain.pricing.collection_bases import BASES
    collector, cache, provider = setup()
    expanded = BaseCollection(collector.service, list(BASES))
    await expanded.initialize()
    assert len(cache.jobs) == 170  # This fixture enables only GasBuddy.
    assert len({job["base"] for job in cache.jobs.values()}) == 85


def test_all_fuel_waze_job_uses_distinct_cache_namespace_and_no_duplicate_grade_query():
    collector, cache, provider = setup()
    collector.service.waze = object()
    expanded = BaseCollection(collector.service, ["la"])
    jobs = [job for job in expanded.jobs.values() if job.source == "waze"]
    assert len(jobs) == 1 and jobs[0].fuel == "all"
    assert jobs[0].raw_key.startswith("waze:all-fuels-v1:")

@pytest.mark.parametrize("reason", ["background_daily_budget_exhausted", "background_budget_exhausted",
                                   "request_budget_exhausted", "background_wait_exhausted", "mandatory_budget_reserved"])
async def test_local_budget_deferrals_preserve_provider_health(reason):
    from gaswise.domain.ports import ProviderError
    collector, cache, provider = setup()
    await collector.initialize()
    async def deferred(*args, **kwargs):
        raise ProviderError("gasbuddy_" + reason)
    cache.get = deferred
    assert not await collector.step()
    assert cache.saved[0][2:4] == (60, "gasbuddy_" + reason)
    assert not background_acquisition.get()


async def test_lane_outage_defers_quickly_without_marking_provider_failure():
    from gaswise.domain.ports import ProviderError
    collector, cache, provider = setup()
    await collector.initialize()
    async def deferred(*args, **kwargs):
        raise ProviderError("pricing_egress_unavailable")
    cache.get = deferred
    assert not await collector.step()
    # Operator-side lane outage: retry in a minute, not an hour, with no failure code.
    assert cache.saved[0][2:4] == (60, "pricing_egress_unavailable")


async def test_transport_failure_retries_soon_when_another_exit_exists():
    from gaswise.domain.ports import ProviderError
    for lanes, delay in ((2, 60), (1, 3600)):
        cache, provider = Cache(), Provider()
        service = SimpleNamespace(shared_cache=cache, gasbuddy=provider, maps_web=None, waze=None,
                                  background_gasbuddy_slot=asyncio.Semaphore(1), source_slots={})
        collector = BaseCollection(service, ["la", "irvine", "sd"], egress_lanes=lanes)
        await collector.initialize()
        async def unavailable(*args, **kwargs):
            raise ProviderError("gasbuddy_http_unavailable")
        cache.get = unavailable
        assert not await collector.step()
        # Still a recorded provider failure, but the quarantined exit lets a
        # pooled deployment retry promptly on another lane.
        assert cache.saved[0][2:4] == (delay, "collection_failed")
        assert cache.saved[0][6]["failure_code"] == "gasbuddy_http_unavailable"


async def test_pacing_pauses_optional_jobs_but_allows_due_mandatory_work():
    collector, cache, provider = setup()
    await collector.initialize()
    state = {"used": 0, "background_day_used": 0, "background_pacing_seconds": 2000}
    async def budget_state(source):
        return state
    cache.budget_state = budget_state
    assert not await collector.step()
    assert not provider.calls
    state["mandatory_due"] = True
    assert await collector.step()
    assert len(provider.calls) == 1


def test_isolated_radius_plan_expands_edges_without_adding_jobs_or_request_reserve():
    from gaswise.domain.pricing.collection_bases import BASES

    collector, _, _ = setup()
    collector.service.maps_web = object()
    collector.service.waze = object()
    legacy = collection_jobs(collector.service, list(BASES), coverage_strategy="legacy")
    adaptive = collection_jobs(collector.service, list(BASES), coverage_strategy="isolated_radius_v1")

    assert len(legacy) == len(adaptive) == 340
    assert sum(job.request_reserve for job in legacy.values()) == 2125
    assert sum(job.request_reserve for job in adaptive.values()) == 2125
    assert adaptive["blythe:regular:gasbuddy"].query.radius_meters > 20000
    assert adaptive["la:regular:gasbuddy"].query.radius_meters == legacy["la:regular:gasbuddy"].query.radius_meters
    assert max(job.query.radius_meters for job in adaptive.values()) <= 20600


def test_collection_rate_budget_guard_rejects_plan_before_any_provider_work():
    collector, _, _ = setup()
    with pytest.raises(ValueError, match="request reserve"):
        BaseCollection(collector.service, ["la", "irvine", "sd"], cycle_request_budget=23)


async def test_status_exposes_rollback_friendly_batch_plan_without_changing_smart_contract():
    collector, cache, _ = setup()
    collector = BaseCollection(
        collector.service,
        ["la", "blythe"],
        coverage_strategy="isolated_radius_v1",
        cycle_request_budget=100,
    )
    await collector.initialize()
    status = await collector.status()
    assert status["coverage_plan"]["strategy"] == "isolated_radius_v1"
    assert status["coverage_plan"]["rollback_strategy"] == "legacy"
    assert status["coverage_plan"]["request_reserve"] == 36
    assert status["coverage_plan"]["expanded_bases"] == ["blythe", "la"]
    assert cache.jobs["blythe:regular:gasbuddy"]["descriptor"]["radius_meters"] > 20000






async def repair_setup(covered=False):
    collector, cache, provider = setup()
    await collector.initialize()
    db = cache._db
    query = GasBuddySearch(origin={'lat': 34.04876, 'lng': -118.28225}, fuel_type='premium',
                           max_results=200, include_payment_variants=True, payment_type='cash_or_credit',
                           radius_meters=1500)
    repair = dict(id='hotspot:dtla:premium:10929', base='la', fuel='premium',
                  descriptor=query.model_dump_json(), coverage_station_id='10929')
    async def execute(method, *args):
        if method == 'claim_base_job':
            return repair['id']
        if method == 'hotspot_job':
            return repair
        if method == 'hotspot_covered':
            assert args == ('10929', 'premium')
            return covered
        return await db(method, *args)
    cache._db = AsyncMock(side_effect=execute)
    return collector, cache, provider


async def test_city_result_that_omits_target_is_not_daily_station_success():
    collector, cache, provider = await repair_setup()
    assert not await collector.step()
    assert cache.saved[0][2:4] == (3600, 'coverage_missing')
    assert provider.calls[0].origin.lat == 34.04876
    assert provider.calls[0].max_pages == 1
    assert provider.calls[0].include_payment_variants


async def test_actual_daily_station_observation_completes_repair():
    collector, cache, provider = await repair_setup(covered=True)
    assert await collector.step()
    assert cache.saved[0][2:4] == (60, None)


async def test_repair_does_not_bypass_shared_budget():
    collector, cache, provider = await repair_setup()
    cache.used = 6
    assert not await collector.step()
    assert not provider.calls
    assert not cache.saved


def test_maps_collection_uses_one_all_fuel_job_with_bounded_premium_details():
    collector, _, _ = setup()
    collector.service.maps_web = object()
    jobs = [j for j in collection_jobs(collector.service, ['la']).values() if j.source == 'maps']
    assert len(jobs) == 1
    assert jobs[0].fuel == 'all'
    assert jobs[0].query.fuel_type == 'premium'
    assert jobs[0].query.detail_limit == 3
    assert jobs[0].request_reserve == 4
    assert jobs[0].raw_key.startswith('maps:all-fuels-v1:')


async def test_slow_gasbuddy_does_not_block_maps_worker_and_shutdown_releases_attempt():
    collector, cache, provider = setup()
    entered, maps_entered = asyncio.Event(), asyncio.Event()
    original = provider.prices
    async def slow(query):
        entered.set()
        await asyncio.Event().wait()
        return await original(query)
    provider.prices = slow
    class Maps:
        async def prices(self, query):
            maps_entered.set()
            return SimpleNamespace(all_prices=[], stations=[])
    collector.service.maps_web = Maps()
    collector.service.source_slots['maps'] = asyncio.Semaphore(1)
    collector = BaseCollection(collector.service, ['irvine'])
    await collector.initialize()
    task = asyncio.create_task(collector.run())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await asyncio.wait_for(maps_entered.wait(), 1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert any(args[3] == 'service_shutdown' for args in cache.saved)
    assert not background_acquisition.get()
