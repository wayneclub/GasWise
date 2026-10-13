"""Opt-in integration against the existing operator PostgreSQL; creates no containers."""

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.sources import GasBuddySearch
from gaswise.domain.ports import ProviderError
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.services.pricing.shared_cache import SharedPricingCache
from tests.support.smart import RawGasBuddy

pytestmark = pytest.mark.skipif(not os.environ.get("GASWISE_TEST_DATABASE_URL"), reason="Existing PostgreSQL test connection not configured")


async def test_existing_postgres_shares_results_refresh_leases_budget_and_cleans_old_quotes():
    store = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    other = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    first, second = SharedPricingCache(store), SharedPricingCache(other)
    suffix = uuid.uuid4().hex
    raw_key = "gasbuddy:integration-test:" + suffix
    key = hashlib.sha256(("pricing-v1:" + raw_key).encode()).hexdigest()
    source = "integration_" + suffix
    station_id = "integration_" + suffix
    provider = RawGasBuddy()
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def load():
        calls.append(1)
        started.set()
        await release.wait()
        value = await provider.prices(GasBuddySearch(origin=Point(lat=34,lng=-118)))
        for quote in value.prices:
            quote.id = station_id
        return value

    try:
        one = asyncio.create_task(first.get("gasbuddy", raw_key, load))
        await started.wait()
        two = asyncio.create_task(second.get("gasbuddy", raw_key, load))
        await asyncio.sleep(.15)
        assert len(calls) == 1
        release.set()
        (a, hit_a), (b, hit_b) = await asyncio.gather(one,two)
        assert not hit_a and hit_b and a.prices == b.prices
        again, hit = await second.get("gasbuddy", raw_key, load)
        assert hit and len(calls) == 1
        assert again.prices[0].price_updated_at == a.prices[0].price_updated_at
        # Stale-while-refresh returns immediately and only one process takes the lease.
        await store.pool.execute("UPDATE gaswise.query_cache SET fresh_until=now()-interval '1 second',lease_until=NULL WHERE key=$1",key)
        release.clear()
        started.clear()
        old_a, old_b = await asyncio.gather(first.get("gasbuddy", raw_key, load), second.get("gasbuddy", raw_key, load))
        await asyncio.wait_for(started.wait(), 8)
        assert len(calls) == 2 and old_a[1] and old_b[1]
        assert "background" in old_a[0].warnings[-1]
        release.set()
        await asyncio.gather(*first.tasks,*second.tasks)
        assert (await second.get("gasbuddy",raw_key,load))[1]
        assert len(calls) == 2
        # New connections after a process restart still use the persisted response.
        restarted = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
        try:
            assert (await SharedPricingCache(restarted).get("gasbuddy",raw_key,load))[1]
        finally:
            await restarted.close()
        assert await store.claim(key,"gasbuddy","lease-test-owner")
        assert await other.renew(key,"lease-test-owner")
        assert not await other.renew(key,"different-owner")
        await store.release(key,"lease-test-owner")
        await store.pool.execute("UPDATE gaswise.stations SET canonical_id='google_places:integration-test' WHERE station_id=$1",station_id)
        assert await other.mappings("gasbuddy_web",[station_id]) == {station_id:"google_places:integration-test"}
        await store.consume(source,1)
        with pytest.raises(ProviderError, match="budget_exhausted"):
            await other.consume(source,1)
        await store.cooldown(source,300)
        with pytest.raises(ProviderError,match="rate_limited"):
            await other.consume(source,100)
        # Expiration deletes only prices, retaining station identity and mapping.
        await store.pool.execute("UPDATE gaswise.quotes SET expires_at=now()-interval '1 second' WHERE station_id=$1",station_id)
        payload = (await store.read(key)).payload
        payload["prices"][0]["price_updated_at"]=(datetime.now(UTC)-timedelta(days=4)).isoformat()
        import json
        await store.pool.execute("UPDATE gaswise.query_cache SET payload=$2::jsonb WHERE key=$1",key,json.dumps(payload))
        assert not (await store.read(key)).payload["prices"]
        await store.cleanup()
        assert not await store.pool.fetchval("SELECT count(*) FROM gaswise.quotes WHERE station_id=$1",station_id)
        assert await store.pool.fetchval("SELECT count(*) FROM gaswise.stations WHERE station_id=$1",station_id) == 1
        assert not (await store.read(key)).payload["prices"]
    finally:
        release.set()
        await first.close()
        await second.close()
        await store.pool.execute("DELETE FROM gaswise.query_cache WHERE key=$1",key)
        await store.pool.execute("DELETE FROM gaswise.quotes WHERE station_id=$1",station_id)
        await store.pool.execute("DELETE FROM gaswise.stations WHERE station_id=$1",station_id)
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1",source)
        await other.close()
        await store.close()
