import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.smart import SmartSearch
from gaswise.domain.ports import ProviderError
from gaswise.services.pricing.cache import TTLCache
from gaswise.services.pricing.smart import SmartService
from tests.support.smart import CountingProvider, MapsInventory, RawGasBuddy


def test_cache_is_bounded_expires_and_returns_isolated_values():
    now = [0]
    cache = TTLCache(capacity=2, clock=lambda: now[0])
    original = {"prices": [1], "updated": "original"}
    cache.put("a", original, 90)
    original["prices"].append(2)
    held = cache.get("a")
    held["prices"].append(3)
    assert cache.get("a")["prices"] == [1]
    cache.put("b", {}, 90)
    cache.put("c", {}, 90)
    assert cache.get("a") is None
    now[0] = 90
    assert cache.get("b") is None and not cache.entries


async def test_repeat_and_payment_changes_reuse_prices_and_routes_force_only_refreshes_prices():
    maps, gb, router = MapsInventory(), RawGasBuddy(), CountingProvider()
    service = SmartService(b"test", "prices_only", maps_web=maps, gasbuddy=gb, router=router)
    query = SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, allow_unknown_payment=True, mpg="25")
    first = await service.search(query)
    counts = maps.calls, gb.calls, router.routes
    second = await service.search(query.model_copy(update={"payment_type": "cash", "gallons": Decimal("12")}))
    assert (maps.calls, gb.calls, router.routes) == counts
    assert not any(second.upstream_calls.values())
    assert second.cache_hits >= 2
    assert second.snapshot.stations[0].price_updated_at == first.snapshot.stations[0].price_updated_at
    assert second.snapshot.stations[0].fetched_at == first.snapshot.stations[0].fetched_at
    await service.search(query.model_copy(update={"force_refresh": True}))
    assert (maps.calls, gb.calls) == (counts[0] + 1, counts[1] + 1)
    assert router.routes == counts[2]
    await service.close()
    assert not service.cache.entries


async def test_cache_expiry_loads_new_prices_and_failures_have_a_short_cooldown():
    service = SmartService(b"test", "prices_only")
    now, calls = [0], []
    service.cache.clock = service.failures.clock = lambda: now[0]

    async def source():
        calls.append(1)
        return {"price": len(calls)}

    assert await service.cached("public-source-query", source) == ({"price": 1}, False)
    assert await service.cached("public-source-query", source) == ({"price": 1}, True)
    now[0] = 90
    assert await service.cached("public-source-query", source) == ({"price": 2}, False)

    async def rejected():
        calls.append(1)
        raise ProviderError("rejected")

    for _ in range(2):
        with pytest.raises(ProviderError):
            await service.cached("rejected-source", rejected)
    assert len(calls) == 3
    now[0] += 30
    with pytest.raises(ProviderError):
        await service.cached("rejected-source", rejected)
    assert len(calls) == 4
    with pytest.raises(ProviderError):
        await service.cached("rejected-source", rejected, refresh=True)
    assert len(calls) == 5


async def test_shared_cache_load_survives_one_cancelled_waiter():
    service = SmartService(b"test", "prices_only")
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def source():
        calls.append(1)
        started.set()
        await release.wait()
        return [1]

    first = asyncio.create_task(service.cached("public-query", source))
    await started.wait()
    second = asyncio.create_task(service.cached("public-query", source))
    await asyncio.sleep(0)
    first.cancel()
    release.set()
    await asyncio.gather(first, return_exceptions=True)
    assert await second == ([1], True)
    assert len(calls) == 1


async def test_cache_does_not_make_stale_quotes_eligible():
    maps = MapsInventory()
    service = SmartService(b"test", "prices_only", maps_web=maps, router=CountingProvider())
    query = SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, allow_unknown_payment=True, mpg="25")
    first = await service.search(query)
    # Hold the real source age intact while a newer collection/check happens.
    for _, value in service.cache.entries.values():
        if hasattr(value, "stations"):
            for station in value.stations:
                station.price_updated_at = datetime.now(UTC) - timedelta(days=2)
    second = await service.search(query)
    assert maps.calls == 1
    assert second.cache_hits > 0
    assert not second.ranking.results
    assert first.ranking.results


async def test_unavailable_source_cooldown_reduces_requests_without_claiming_prices():
    class RejectedGasBuddy:
        calls = 0

        async def prices(self, query):
            self.calls += 1
            raise ProviderError("gasbuddy_http_bootstrap_challenge")

    gb, maps = RejectedGasBuddy(), MapsInventory()
    service = SmartService(b"test", "prices_only", gasbuddy=gb, maps_web=maps)
    query = SmartSearch(origin=Point(lat=34, lng=-118))
    first = await service.search(query)
    second = await service.search(query)
    assert gb.calls == maps.calls == 1
    assert not any(second.upstream_calls.values())
    assert second.cache_hits == 2
    failed = next(s for s in second.snapshot.source_statuses if s.source == "gasbuddy_web")
    assert failed.status == "unavailable" and failed.quote_count == 0
    assert first.snapshot.stations[0].price_updated_at == second.snapshot.stations[0].price_updated_at
    await service.search(query.model_copy(update={"force_refresh": True}))
    assert gb.calls == maps.calls == 2
