"""Isolated integration proof in an isolated schema; zero upstream calls.

Run inside the backend container with this checkout on PYTHONPATH. All fixture
DDL/data is removed in a finally block. Production pricing tables are never written.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from importlib.resources import files
from uuid import uuid4

import asyncpg

from gaswise.app.settings import Settings
from gaswise.providers.storage.postgres import PostgresPricingCache


class IsolatedStore:
    def __init__(self, connection, schema):
        self.connection, self.schema = connection, schema

    @asynccontextmanager
    async def acquire(self):
        async with self.connection.acquire() as connection:
            yield IsolatedStore(connection, self.schema)

    def transaction(self, **kwargs):
        return self.connection.transaction(**kwargs)

    def __getattr__(self, name):
        async def execute(sql, *args):
            return await getattr(self.connection, name)(sql.replace('gaswise.', self.schema + '.'), *args)
        return execute


async def main():
    connection = await asyncpg.connect(Settings().database_url.get_secret_value())
    schema = 'validation_' + uuid4().hex
    raw_pool = await asyncpg.create_pool(Settings().database_url.get_secret_value(), min_size=1, max_size=4)
    pool = IsolatedStore(raw_pool, schema)
    try:
        ddl = files('gaswise.providers.storage').joinpath('schema.sql').read_text()
        await connection.execute(ddl.replace('gaswise', schema))
        store = PostgresPricingCache(pool)
        now = await pool.fetchval('SELECT now()') - timedelta(seconds=1)
        quote = dict(source='gasbuddy_web', id='10929', name='Speedway Express', fuel_type='premium',
                     payment_type='credit', price_per_gallon='6.15', canonical_id='validation:station',
                     price_updated_at=(now-timedelta(hours=49)).isoformat(),
                     fetched_at=(now-timedelta(days=2)).isoformat(),
                     location={'lat': 34.04876, 'lng': -118.28225})
        await store._observe(pool, [quote])
        await store._observe(pool, [{**quote, 'fetched_at': now.isoformat()}])
        await store._observe(pool, [{**quote, 'fetched_at': now.isoformat()}])
        assert await pool.fetchval('SELECT count(*) FROM gaswise.quote_history') == 1
        assert await pool.fetchval('SELECT count(*) FROM gaswise.quote_daily') == 2
        history = await store.price_history(None, 'gasbuddy_web', '10929', 'premium', 7)
        assert len(history['observations']) == 2
        assert all(r['observation_kind'] == 'daily_check' for r in history['observations'])
        assert len({r['reported_at'] for r in history['observations']}) == 1
        assert await store.hotspot_covered('10929', 'premium')
        assert not await store.hotspot_covered('10929', 'regular')
        print('PASS daily history: unchanged report, two actual fetch days, no fabricated middle day, replay deduplicated')
        canonical = await store.price_history('validation:station', 'gasbuddy_web', '10929', 'premium', 7)
        assert len(canonical['observations']) == 2
        cash = {**quote, 'payment_type': 'cash', 'price_per_gallon': '6.05',
                'fetched_at': (now-timedelta(days=1)).isoformat()}
        await store._observe(pool, [cash])
        assert not await store.hotspot_covered('10929', 'premium')
        await store._observe(pool, [{**cash, 'fetched_at': now.isoformat()}])
        assert await store.hotspot_covered('10929', 'premium')
        assert await pool.fetchval("SELECT ('2026-11-01 06:59:00+00'::timestamptz AT TIME ZONE 'America/Los_Angeles')::date < ('2026-11-01 07:01:00+00'::timestamptz AT TIME ZONE 'America/Los_Angeles')::date")
        assert await pool.fetchval("SELECT ('2026-11-01 08:30:00+00'::timestamptz AT TIME ZONE 'America/Los_Angeles')::date = ('2026-11-01 09:30:00+00'::timestamptz AT TIME ZONE 'America/Los_Angeles')::date")
        await pool.execute("""INSERT INTO gaswise.quote_history
            SELECT 'legacy-fixture',source,station_id,canonical_id,fuel_type,payment_type,purchase_condition,
                6.25,$1,$1,$1,attributes FROM gaswise.quote_history LIMIT 1""", now-timedelta(days=4))
        legacy = await store.price_history('validation:station', 'gasbuddy_web', '10929', 'premium', 7)
        assert any(r['observation_kind'] == 'report' and r['price'] == '6.25' for r in legacy['observations'])
        print('PASS canonical history, legacy fallback, separate cash/card coverage, LA midnight and daylight saving')


        # Replaying an older payload today must not manufacture today's coverage.
        await pool.execute('DELETE FROM gaswise.quote_daily WHERE first_seen_at>$1', now-timedelta(days=1))
        await store._observe(pool, [quote])
        assert not await store.hotspot_covered('10929', 'premium')
        await store.sync_hotspot_jobs(request_budget=2)
        assert await pool.fetchval('SELECT count(*) FROM gaswise.base_collection_jobs WHERE enabled') == 1
        await store.sync_hotspot_jobs(request_budget=4)
        assert await pool.fetchval('SELECT count(*) FROM gaswise.base_collection_jobs WHERE enabled') == 2
        claimed = await asyncio.gather(*(store.claim_base_job(owner, ['gasbuddy'])
                                        for owner in ('worker-one', 'worker-two', 'worker-three')))
        owners = {job: owner for job, owner in zip(claimed, ('worker-one', 'worker-two', 'worker-three')) if job}
        assert len(owners) == 2 and claimed.count(None) == 1
        first, second = owners
        assert not await store.finish_base_job(first, 'wrong-owner', 60, None, 1, 1)
        assert await store.finish_base_job(first, owners[first], 3600, 'coverage_missing', 0, 0)
        print('PASS target coverage: cache replay stays missing; distinct worker claims and owner-checked completion')

        # Three genuine missing-result attempts exhaust today's per-target retry allowance.
        for i in range(2):
            await pool.execute("INSERT INTO gaswise.collection_runs(job_id,owner,base,source,fuel,outcome,reason) VALUES($1,$2,'la','gasbuddy','premium','deferred','coverage_missing')", first, f'fixture-{i}')
        await store.sync_hotspot_jobs()
        assert not await pool.fetchval('SELECT enabled FROM gaswise.base_collection_jobs WHERE id=$1', first)
        # An actual same-day observation suppresses queued work for the other grade.
        await store.finish_base_job(second, owners[second], 60, 'coverage_missing', 0, 0)
        await store._observe(pool, [{**row, 'fetched_at': now.isoformat(), 'fuel_type': second.split(':')[2]}
                                    for row in (quote, cash)])
        await store.sync_hotspot_jobs()
        assert not await pool.fetchval('SELECT enabled FROM gaswise.base_collection_jobs WHERE id=$1', second)
        status = await store.hotspot_status()
        assert status['target_station_fuels'] == 2 and status['checked_today'] == 1
        assert len(status['missing']) == 1
        assert status['coverage'] == 'partial'
        print('PASS repair queue: retry cap, neighbouring-query completion, honest partial coverage')

        # Source cooldown and mandatory reservations remain global.
        await pool.execute("INSERT INTO gaswise.source_limits(source) VALUES('gasbuddy') ON CONFLICT DO NOTHING")
        await store.cooldown('gasbuddy', 120)
        try:
            await store.consume('gasbuddy', 12, background=True, mandatory=True)
        except Exception as error:
            assert 'rate_limited' in str(error)
        else:
            raise AssertionError('mandatory repair bypassed cooldown')
        print('PASS source cooldown: mandatory repair is still blocked')
    finally:
        await raw_pool.close()
        await connection.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        await connection.close()
    print('PASS isolated schema and fixtures removed; zero upstream requests')


asyncio.run(main())
