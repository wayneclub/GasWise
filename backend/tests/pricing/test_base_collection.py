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
            return next(iter(self.jobs), None)
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
    assert cache.saved[0][3] == "source_budget_deferred"
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
