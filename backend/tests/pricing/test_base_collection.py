import asyncio
from types import SimpleNamespace

import pytest

from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.services.pricing.base_collection import BaseCollection


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
        return SimpleNamespace(prices=[SimpleNamespace(id="station")])


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
    assert all(args[4:] == (1, 1) for args in cache.saved)
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


async def test_cancellation_releases_job_without_marking_completion():
    collector, cache, provider = setup()
    await collector.initialize()
    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError
    cache.get = cancel
    with pytest.raises(asyncio.CancelledError):
        await collector.step()
    assert cache.saved[0][3] == "interrupted"
    assert not background_acquisition.get()


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
