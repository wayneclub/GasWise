"""Verify scheduler context and budgets with isolated DB fixtures; zero provider HTTP."""

import asyncio
import hashlib
import json
import uuid

from gaswise.app.settings import Settings
from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.providers.storage.request_budget import RequestBudget
from gaswise.services.pricing.hot_refresh import HotQueryRefresh
from gaswise.services.pricing.shared_cache import SharedPricingCache


async def main():
    settings = Settings()
    store = await PostgresPricingCache.connect(settings.database_url.get_secret_value())
    source = 'pilot_runtime_' + uuid.uuid4().hex
    raw_key = 'waze:pilot-runtime:' + uuid.uuid4().hex
    key = hashlib.sha256(('pricing-v1:' + raw_key).encode()).hexdigest()
    shared = SharedPricingCache(store)
    now = [0]
    budget = RequestBudget(store, {source: 10}, background_daily_limit=3)
    original_state = shared.budget_state
    async def state(_):
        return await original_state(source)
    shared.budget_state = state
    warmer = HotQueryRefresh(shared, limits={'waze': 10}, daily_limit=3, clock=lambda: now[0])
    observations = []
    async def load():
        observations.append(background_acquisition.get())
        await budget.before(source)
        return []
    try:
        await shared.get('waze', raw_key, load)
        await store.pool.execute("UPDATE gaswise.query_cache SET fresh_until=now()-interval '1 second',lease_until=NULL WHERE key=$1", key)
        for _ in range(12):
            warmer.observe('waze', raw_key, load)
        now[0] = 900
        assert await warmer.step()
        await asyncio.gather(*shared.tasks)
        assert observations == [False, True]
        assert (await store.budget_state(source))['background_used'] == 1
        # Known source pressure pauses scheduler without another acquisition.
        await store.pool.execute('UPDATE gaswise.source_limits SET request_count=5 WHERE source=$1', source)
        now[0] = 1800
        assert not await warmer.step()
        assert observations == [False, True]
        print(json.dumps({'runtime_background_context': True, 'shared_actual_request_counter': True,
                          'adaptive_pressure_pause': True, 'provider_http_requests': 0,
                          'evidence': 'isolated fixture acquisition against existing production PostgreSQL'}))
    finally:
        await shared.close()
        await store.pool.execute('DELETE FROM gaswise.query_cache WHERE key=$1', key)
        await store.pool.execute('DELETE FROM gaswise.source_limits WHERE source=$1', source)
        await store.close()
asyncio.run(main())
