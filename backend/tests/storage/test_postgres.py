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
from gaswise.domain.pricing.alerts import purchase_condition_key
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
        await store.pool.execute("DELETE FROM gaswise.station_history WHERE station_id=$1",station_id)
        await store.pool.execute("DELETE FROM gaswise.stations WHERE station_id=$1",station_id)
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1",source)
        await other.close()
        await store.close()


async def test_existing_postgres_background_caps_are_shared_and_foreground_keeps_capacity():
    store = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    other = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    source = "integration_background_" + uuid.uuid4().hex
    try:
        async def consume(cache):
            try:
                await cache.consume(source, 10, background=True, background_daily_limit=3)
                return True
            except ProviderError:
                return False

        results = await asyncio.gather(*(consume(store if i % 2 else other) for i in range(6)))
        assert sum(results) == 2  # 20% of the shared minute budget.
        assert (await other.budget_state(source))["background_used"] == 2
        await other.consume(source, 10)  # Foreground is still allowed.
        await store.pool.execute("UPDATE gaswise.source_limits SET window_start=now()-interval '61 seconds' WHERE source=$1", source)
        assert await consume(other)
        assert not await consume(store)  # Daily cap survives minute reset.
        assert (await store.budget_state(source))["background_day_used"] == 3
        await store.pool.execute("UPDATE gaswise.source_limits SET background_day_start=now()-interval '25 hours',window_start=now()-interval '61 seconds' WHERE source=$1", source)
        assert await consume(other)
        # Foreground pressure independently prevents a background request.
        await store.pool.execute("UPDATE gaswise.source_limits SET request_count=5,background_count=0 WHERE source=$1", source)
        assert not await consume(store)
        await other.consume(source, 10)
    finally:
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1", source)
        await other.close()
        await store.close()


async def test_daily_ramp_persists_reviews_keeps_usage_and_reduces_after_rejection():
    store = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    other = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    source = "integration_ramp_" + uuid.uuid4().hex
    try:
        await store.configure_daily_ramp([source], 80, 40, 800)
        await store.pool.execute("""UPDATE gaswise.source_limits SET daily_review_at=now()-interval '25 hours',
            daily_review_requests=80,background_last_request_at=now(),background_day_count=80 WHERE source=$1""", source)
        await asyncio.gather(store.budget_state(source), other.budget_state(source))
        assert (await store.budget_state(source))["daily_limit"] == 160
        assert (await store.budget_state(source))["background_day_used"] == 80
        await other.configure_daily_ramp([source], 80, 40, 800)
        assert (await store.budget_state(source))["daily_limit"] == 160
        await store.consume(source, 100, background=True, background_daily_limit=80)
        assert (await store.budget_state(source))["background_day_used"] == 81
        await other.cooldown(source, 120)
        assert (await store.budget_state(source))["daily_limit"] == 80
        await other.cooldown(source, 120)
        await other.cooldown(source, 120)
        assert (await store.budget_state(source))["daily_limit"] == 40
        assert (await store.budget_state(source))["background_day_used"] == 81
        with pytest.raises(ProviderError, match="rate_limited"):
            await store.consume(source, 100, background=True)
        await store.disable_daily_ramp([source])
        assert (await store.budget_state(source))["daily_limit"] is None
    finally:
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1", source)
        await other.close()
        await store.close()


async def test_smart_alert_postgres_lifecycle_is_authorized_deduplicated_and_cascades():
    store = await PostgresPricingCache.connect(os.environ["GASWISE_TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    installation_id = f"installation_{suffix}"
    token_hash = f"token_{suffix}"
    endpoint_hash = f"endpoint_{suffix}"
    station_id = f"station_{suffix}"
    source = f"integration_{suffix}"
    canonical_id = f"canonical_{suffix}"
    condition = purchase_condition_key(None, 87, "USD", "US_gallon")
    now = datetime.now(UTC)
    attributes = '{"name":"Integration Fuel","octane":87,"currency":"USD","unit":"US_gallon"}'
    try:
        assert await store.create_alert_installation(
            installation_id, token_hash, endpoint_hash, b"encrypted-subscription",
            "America/Los_Angeles", "en",
        ) == installation_id
        assert not await store.update_alert_need(
            installation_id, "wrong-token", "due", "high", now + timedelta(hours=24)
        )
        assert await store.update_alert_need(
            installation_id, token_hash, "due", "high", now + timedelta(hours=24)
        )
        assert await store.set_alert_watch(
            installation_id, token_hash, True, canonical_id, source, station_id,
            "Integration Fuel", "regular", "cash", condition, 10, 10,
        ) is True
        await store.pool.executemany("""
            INSERT INTO gaswise.quote_history
                (observation_key,source,station_id,canonical_id,fuel_type,payment_type,
                 purchase_condition,price_per_gallon,reported_at,first_seen_at,last_seen_at,attributes)
            VALUES($1,$2,$3,$4,'regular','cash',$5,$6,$7,$7,$7,$8::jsonb)
        """, [
            (f"old_{suffix}", source, station_id, canonical_id, condition, "4.30",
             now - timedelta(hours=1), attributes),
            (f"new_{suffix}", source, station_id, canonical_id, condition, "4.10",
             now, attributes),
        ])

        candidate = await store.claim_alert_candidate(f"worker_{suffix}")
        assert candidate is not None
        assert candidate["observation_key"] == f"new_{suffix}"
        assert str(candidate["current_price"]) == "4.10"
        assert str(candidate["previous_price"]) == "4.30"
        payload = {"title": "Integration Fuel dropped", "body": "Save $2.00", "tag": "integration"}
        assert await store.finish_alert_candidate(
            candidate["watch_id"], f"worker_{suffix}", candidate["observation_key"], payload, "push"
        ) is True
        assert await store.claim_alert_candidate(f"other_{suffix}") is None
        inbox = await store.alert_inbox(installation_id, token_hash)
        assert inbox and inbox[0]["title"] == payload["title"]
        assert await store.pool.fetchval(
            "SELECT count(*) FROM gaswise.alert_outbox WHERE installation_id=$1", installation_id
        ) == 1

        assert not await store.disable_alert_installation(installation_id, "wrong-token")
        assert await store.disable_alert_installation(installation_id, token_hash)
        assert await store.pool.fetchval(
            "SELECT count(*) FROM gaswise.alert_watches WHERE installation_id=$1", installation_id
        ) == 0
        assert await store.pool.fetchval(
            "SELECT count(*) FROM gaswise.alert_outbox WHERE installation_id=$1", installation_id
        ) == 0
        assert await store.pool.fetchval(
            "SELECT count(*) FROM gaswise.alert_inbox WHERE installation_id=$1", installation_id
        ) == 0
    finally:
        await store.pool.execute("DELETE FROM gaswise.alert_installations WHERE id=$1", installation_id)
        await store.pool.execute("DELETE FROM gaswise.quote_history WHERE station_id=$1", station_id)
        await store.close()
