import asyncio
from datetime import UTC, datetime

import pytest

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.shared_cache import CachedQuery
from gaswise.services.pricing.shared_cache import SharedPricingCache


class Store:
    def __init__(self):
        self.entries, self.owners = {}, {}
    async def read(self,key):
        return self.entries.get(key)
    async def claim(self,key,source,owner):
        if key in self.owners:
            return False
        self.owners[key] = owner
        return True
    async def save(self,key,source,owner,payload,fresh_seconds):
        assert self.owners[key] == owner
        self.entries[key] = CachedQuery(payload,True,True,datetime.now(UTC))
        return self.entries[key].fetched_at
    async def renew(self,key,owner):
        return self.owners.get(key) == owner
    async def release(self,key,owner):
        if self.owners.get(key) == owner:
            self.owners.pop(key)


async def test_stale_cache_returns_without_waiting_for_refresh_and_coalesces_across_instances():
    store = Store()
    one, two = SharedPricingCache(store), SharedPricingCache(store)
    calls, release = [], asyncio.Event()
    async def load():
        calls.append(1)
        return []
    assert await one.get("waze","same-public-cell",load) == ([],False)
    assert await two.get("waze","same-public-cell",load) == ([],True)
    assert len(calls) == 1
    next(iter(store.entries.values())).fresh = False
    refresh_started = asyncio.Event()
    async def refresh():
        refresh_started.set()
        calls.append(1)
        await release.wait()
        return []
    assert await one.get("waze","same-public-cell",refresh) == ([],True)
    assert await two.get("waze","same-public-cell",refresh) == ([],True)
    await asyncio.wait_for(refresh_started.wait(),1)
    assert len(calls) == 2
    release.set()
    await asyncio.gather(*one.tasks)
    assert await two.get("waze","same-public-cell",refresh) == ([],True)
    assert not store.owners
    await one.close()
    await two.close()


async def test_database_read_failure_never_falls_back_to_repeated_source_fetches():
    class Broken(Store):
        async def read(self,key):
            raise RuntimeError("private DB diagnostics")
    async def source():
        pytest.fail("Upstream must not be called when the shared cache cannot be consulted")
    with pytest.raises(ProviderError,match="shared_pricing_cache_unavailable"):
        await SharedPricingCache(Broken()).get("waze","public-cell",source)


async def test_fixed_collection_waits_for_stale_refresh_before_completion():
    store = Store()
    cache = SharedPricingCache(store)
    async def initial():
        return []
    await cache.get("waze", "fixed-base", initial)
    next(iter(store.entries.values())).fresh = False
    started, release = asyncio.Event(), asyncio.Event()
    async def refresh():
        started.set()
        await release.wait()
        return []
    task = asyncio.create_task(cache.get("waze", "fixed-base", refresh, wait_refresh=True))
    await asyncio.wait_for(started.wait(), 1)
    assert not task.done()
    assert not cache.tasks  # Synchronous completion, not stale-while-revalidate.
    release.set()
    assert await task == ([], False)
    assert next(iter(store.entries.values())).fresh
    await cache.close()
