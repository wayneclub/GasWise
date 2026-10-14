import asyncio

import pytest

from gaswise.services.pricing.hot_refresh import HotQueryRefresh


class Cache:
    def __init__(self):
        self.calls = []

    async def budget_state(self, source):
        return {"used": 0, "background_used": 0, "background_day_used": 0, "blocked_seconds": 0}

    async def get(self, source, key, operation):
        self.calls.append((source, key))
        return await operation(), True


async def test_only_hot_queries_refresh_one_per_step_and_idle_queries_stop():
    now = [0]
    cache = Cache()
    warmer = HotQueryRefresh(cache, clock=lambda: now[0])

    async def load():
        return []

    warmer.observe("maps", "cold", load)
    for key in ("popular-a", "popular-b"):
        for _ in range(12):
            warmer.observe("maps", key, load)
    assert not await warmer.step()
    now[0] = 900
    assert await warmer.step()
    assert len(cache.calls) == 1
    assert await warmer.step()
    assert len(cache.calls) == 2
    assert not await warmer.step()
    now[0] = 3600
    assert not await warmer.step()
    assert not warmer.queries


async def test_registration_is_bounded_and_failures_do_not_retry_each_tick():
    now = [0]
    cache = Cache()
    warmer = HotQueryRefresh(cache, max_queries=1, clock=lambda: now[0])

    async def failure():
        raise RuntimeError("private transport detail")

    for _ in range(12):
        warmer.observe("gasbuddy", "one", failure)
    warmer.observe("maps", "two", failure)
    assert len(warmer.queries) == 1
    now[0] = 900
    assert await warmer.step()
    now[0] = 960
    assert not await warmer.step()
    assert len(cache.calls) == 1


async def test_cancellation_propagates_for_clean_shutdown():
    cache = Cache()
    now = [0]
    warmer = HotQueryRefresh(cache, clock=lambda: now[0])

    async def cancel():
        raise asyncio.CancelledError

    for _ in range(12):
        warmer.observe("maps", "one", cancel)
    now[0] = 900
    with pytest.raises(asyncio.CancelledError):
        await warmer.step()


async def test_demand_slows_down_and_usage_decays_instead_of_permanent_hotness():
    now = [0]
    cache = Cache()
    warmer = HotQueryRefresh(cache, clock=lambda: now[0])

    async def load():
        return []

    for _ in range(3):
        warmer.observe("maps", "cell", load)
    query = next(iter(warmer.queries.values()))
    assert warmer.demand_interval(query) == 3600
    now[0] = 900
    assert not await warmer.step()
    for _ in range(3):
        warmer.observe("maps", "cell", load)
    assert warmer.demand_interval(query) == 1800
    now[0] = 1800
    assert await warmer.step()
    now[0] = 3600
    warmer._prune(now[0])
    assert len(query.uses) == 3
    assert warmer.demand_interval(query) == 3600


async def test_source_pressure_defers_without_io_and_other_source_can_proceed():
    now = [0]
    cache = Cache()

    async def state(source):
        return {"used": 30 if source == "maps" else 0, "background_day_used": 0}

    cache.budget_state = state
    warmer = HotQueryRefresh(cache, clock=lambda: now[0])

    async def load():
        return []

    for source in ("maps", "waze"):
        for _ in range(12):
            warmer.observe(source, source, load)
    now[0] = 900
    assert await warmer.step()
    assert cache.calls == [("waze", "waze")]
    assert warmer.paces["maps"].deferred == 1


async def test_background_operation_inherits_context_and_backoff_recovers_gradually():
    from gaswise.domain.pricing.shared_cache import background_acquisition

    now = [0]
    cache = Cache()
    warmer = HotQueryRefresh(cache, clock=lambda: now[0])
    failing = [True]

    async def load():
        assert background_acquisition.get()
        if failing[0]:
            raise RuntimeError("source failed")
        return []

    for _ in range(12):
        warmer.observe("maps", "one", load)
    now[0] = 900
    assert await warmer.step()
    assert warmer.paces["maps"].not_before == 2700
    assert not background_acquisition.get()
    now[0] = 1800
    assert not await warmer.step()
    now[0] = 2700
    assert await warmer.step()
    assert warmer.paces["maps"].not_before == 6300
    now[0] = 6300
    for _ in range(12):
        warmer.observe("maps", "one", load)
    # Idle registration expires and starts its interval again.
    now[0] = 7200
    failing[0] = False
    assert await warmer.step()
    assert warmer.paces["maps"].failures == 1
    assert warmer.paces["maps"].loads == 1


async def test_daily_budget_stops_background_updates():
    now = [0]
    cache = Cache()

    async def state(source):
        return {"used": 0, "background_day_used": 100}

    cache.budget_state = state
    warmer = HotQueryRefresh(cache, clock=lambda: now[0])

    async def load():
        pytest.fail("No provider request when daily cap is reached")

    for _ in range(12):
        warmer.observe("maps", "one", load)
    now[0] = 900
    assert not await warmer.step()
    assert not cache.calls


async def test_stale_shared_refresh_inherits_background_budget_after_step_returns():
    from gaswise.domain.pricing.shared_cache import background_acquisition
    from gaswise.services.pricing.shared_cache import SharedPricingCache
    from tests.pricing.test_shared_cache import Store

    store = Store()

    async def state(source):
        return {"used": 0, "background_day_used": 0}

    store.budget_state = state
    shared = SharedPricingCache(store)
    now = [0]
    warmer = HotQueryRefresh(shared, clock=lambda: now[0])
    seen = []

    async def load():
        seen.append(background_acquisition.get())
        return []

    await shared.get("waze", "waze:public-cell", load)
    next(iter(store.entries.values())).fresh = False
    for _ in range(12):
        warmer.observe("waze", "waze:public-cell", load)
    now[0] = 900
    assert await warmer.step()
    assert not background_acquisition.get()
    await asyncio.gather(*shared.tasks)
    assert seen == [False, True]
    assert warmer.paces["waze"].loads == 1
    await shared.close()


async def test_waiting_background_gasbuddy_does_not_occupy_foreground_source_slot():
    from gaswise.domain.pricing.shared_cache import background_acquisition
    from gaswise.services.pricing.smart import SmartService

    class Cache:
        async def get(self, source, key, operation):
            return await operation(), False

    service = SmartService(b"test-secret", "prices_only", shared_cache=Cache())
    started, release = asyncio.Event(), asyncio.Event()

    async def background():
        started.set()
        await release.wait()
        return []

    async def foreground():
        return ["foreground-completed"]

    token = background_acquisition.set(True)
    task = asyncio.create_task(service.cached("gasbuddy:background", background))
    background_acquisition.reset(token)
    try:
        await asyncio.wait_for(started.wait(), 1)
        assert await asyncio.wait_for(service.cached("gasbuddy:foreground", foreground), 1) == (["foreground-completed"], False)
    finally:
        release.set()
        await task
