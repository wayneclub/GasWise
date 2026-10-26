"""Integration checks against an explicitly isolated, disposable PostgreSQL database.

Requires GASWISE_TEST_DATABASE_URL. Never point this at the production database.
Does not make provider requests or print connection details.
"""
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from gaswise.contracts.common import Point, Station
from gaswise.contracts.search import Search
from gaswise.contracts.smart import SmartSnapshot
from gaswise.contracts.sources import MapsWebSearch
from gaswise.domain.ports import ProviderError
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.services.pricing.shared_cache import SharedPricingCache
from gaswise.services.pricing.smart import SmartService


async def main():
    dsn = os.environ['GASWISE_TEST_DATABASE_URL']
    if not urlsplit(dsn).path.removeprefix('/').startswith('gaswise_arch_'):
        raise SystemExit('An isolated gaswise_arch_ test database is required')
    import asyncpg
    setup = await asyncpg.connect(dsn)
    try:
        await setup.execute('DROP SCHEMA IF EXISTS gaswise CASCADE')
    finally:
        await setup.close()
    first = await PostgresPricingCache.connect(dsn)
    second = await PostgresPricingCache.connect(dsn)
    try:
        # Shared key survives a second pool/process; no plaintext value is printed.
        key = await first.snapshot_signing_key()
        shared_keys = await asyncio.gather(*(second.snapshot_signing_key() for _ in range(4)))
        assert len(key) == 32 and all(value == key for value in shared_keys)
        snapshot = SmartSnapshot(query=Search(origin=Point(lat=34, lng=-118)), stations=[], source_statuses=[],
                                 collected_at=datetime.now(UTC), expires_at=datetime.now(UTC)+timedelta(minutes=5))
        one, two = SmartService(key, 'prices_only'), SmartService(shared_keys[0], 'prices_only')
        two.verify(snapshot, one.sign(snapshot))
        await one.close()
        await two.close()
        query = MapsWebSearch(origin=Point(lat=34, lng=-118), fuel_type='premium', detail_limit=3)
        def job(fuel):
            return dict(id=f'la:{fuel}:maps', base='la', source='maps', fuel=fuel,
                        population_priority=100, request_reserve=4, mandatory=True,
                        descriptor=query.model_copy(update={'fuel_type': fuel if fuel != 'all' else 'premium'}).model_dump(mode='json'))
        await first.configure_base_jobs([job('regular'), job('premium')])
        await first.pool.execute("UPDATE gaswise.base_collection_jobs SET last_success=now()-interval '4 hours',next_due=now()+interval '20 hours'")
        await first.configure_base_jobs([job('all')])
        migrated = await first.pool.fetchrow("SELECT *,next_due>now() AS future FROM gaswise.base_collection_jobs WHERE fuel='all'")
        assert migrated['last_success'] and migrated['future'] and migrated['enabled']
        assert migrated['schedule_inherited_from'] == ['la:premium:maps', 'la:regular:maps']
        assert await first.pool.fetchval("SELECT count(*) FROM gaswise.base_collection_jobs WHERE enabled") == 1
        # Stable owner and incompatible descriptors never inherit stale schedules.
        changed = job('all')
        changed['descriptor']['radius_meters'] = 25000
        await first.pool.execute("UPDATE gaswise.base_collection_jobs SET last_success=NULL,next_due=now() WHERE fuel='all'")
        await first.configure_base_jobs([changed])
        assert await first.pool.fetchval("SELECT last_success FROM gaswise.base_collection_jobs WHERE fuel='all'") is None

        for _ in range(20):
            await first.consume('waze', 1000, background=True, background_daily_limit=100, purpose='revalidation')
        try:
            await second.consume('waze', 1000, background=True, background_daily_limit=100)
            raise AssertionError('Optional allowance was bypassed')
        except ProviderError as error:
            assert str(error) == 'waze_optional_daily_budget_exhausted'
        for _ in range(80):
            await second.consume('waze', 1000, background=True, background_daily_limit=100, purpose='city')
        try:
            await first.consume('waze', 1000, background=True, background_daily_limit=100, purpose='city', mandatory=True)
            raise AssertionError('Global daily allowance was bypassed')
        except ProviderError as error:
            assert str(error) == 'waze_background_daily_budget_exhausted'
        state = await first.budget_state('waze')
        assert state['background_day_used'] == 100
        assert state['background_usage'] == {'city': 80, 'revalidation': 20}
        # A new daily window resets purpose counters atomically.
        await first.pool.execute("UPDATE gaswise.source_limits SET background_day_start=now()-interval '25 hours' WHERE source='waze'")
        await first.consume('waze', 1000, background=True, background_daily_limit=100)
        assert (await first.budget_state('waze'))['background_usage'] == {'demand': 1}

        warm_key = hashlib.sha256(b'architecture-fixture').hexdigest()
        await first.observe_warm_query(warm_key, 'maps', 'maps:' + query.model_dump_json(), 900, 4)
        assert (await first.warming_plan('maps')) == {'active': 1, 'request_cost': 4}
        await first.pool.execute("UPDATE gaswise.warm_queries SET next_due=now()-interval '1 second'")
        claimed = await first.claim_warm_query('owner', ['maps'])
        assert claimed['request_cost'] == 4
        assert await second.claim_warm_query('other', ['maps']) is None
        await first.finish_warm_query(warm_key, 'owner', 5400)
        await first.pool.execute("UPDATE gaswise.warm_queries SET last_requested_at=now()-interval '2 days',next_due=now()-interval '1 second'")
        assert (await first.warming_plan('maps'))['active'] == 0
        assert (await first.warm_query_status())['active'] == 1
        assert await first.claim_warm_query('owner', ['maps']) is None
        await first.observe_warm_query(warm_key, 'maps', 'maps:' + query.model_dump_json(), 900, 4)
        assert await first.claim_warm_query('owner', ['maps']) is not None
        await first.finish_warm_query(warm_key, 'owner', 5400)
        progress = await first.batch_progress()
        assert progress['jobs'][0]['city_jobs'] == 1
        # Unknown source report time is distinct from a recent dated report.
        now = datetime.now(UTC)
        await first.observe([Station(id='test', source='waze', name='Fixture', fuel_type='regular',
                                     location=Point(lat=34, lng=-118), price_per_gallon='4.50', fetched_at=now)])
        prices = (await first.batch_progress())['daily_prices']
        assert prices[0]['undated'] == 1 and prices[0]['recent_reports'] == 0
        cache_one, cache_two = SharedPricingCache(first), SharedPricingCache(second)
        source_calls = []
        async def unavailable():
            source_calls.append(1)
            raise ProviderError('waze_reauthentication_required')
        for cache in (cache_one, cache_two):
            try:
                await asyncio.wait_for(cache.get('waze', 'failure-isolation-fixture', unavailable), .5)
                raise AssertionError('Failed source became a success')
            except ProviderError as error:
                assert str(error) == 'waze_reauthentication_required'
        assert source_calls == [1]
        failure_key = hashlib.sha256(b'pricing-v1:failure-isolation-fixture').hexdigest()
        await first.pool.execute("UPDATE gaswise.query_cache SET failure_until=now()-interval '1 second',lease_until=NULL WHERE key=$1", failure_key)
        async def recovered():
            return []
        assert await cache_two.get('waze', 'failure-isolation-fixture', recovered) == ([], False)
        assert (await first.read(failure_key)).failure is None
        await cache_one.close()
        await cache_two.close()
        print(json.dumps({'signing_key': 'shared', 'migration': 'compatible_only',
                          'optional_cap': '20/100', 'city_capacity': '80/100',
                          'failure_isolation': 'passed', 'window_reset': 'passed', 'warm_cost_and_lease': 'passed', 'freshness': 'passed'}))
    finally:
        await second.close()
        await first.close()


if __name__ == '__main__':
    asyncio.run(main())
