"""Low-frequency fixed-cell patrol under the existing optional background allowance."""
import asyncio
import json
import logging
import uuid

from gaswise.contracts.sources import MapsWebSearch
from gaswise.domain.pricing.background_policy import optional_allowance
from gaswise.domain.pricing.shared_cache import acquisition_purpose, background_acquisition

logger = logging.getLogger(__name__)


class InventoryPatrol:
    def __init__(self, service, daily_limit=100):
        self.service, self.cache, self.daily_limit = service, service.shared_cache, daily_limit

    async def step(self):
        state = await self.cache.budget_state('maps')
        usage = state.get('background_usage', {})
        daily = state.get('daily_limit') or self.daily_limit
        if (state.get('blocked_seconds', 0) or state['background_day_used'] >= daily
                or sum(usage.get(key,0) for key in ('demand','revalidation')) >= optional_allowance(daily)):
            return False
        owner = uuid.uuid4().hex
        job = await self.cache._db('claim_inventory_patrol', owner)
        if job is None:
            return False
        token = background_acquisition.set(True)
        purpose = acquisition_purpose.set('demand')
        success = False
        try:
            query = MapsWebSearch.model_validate(json.loads(job['descriptor']) if isinstance(job['descriptor'],str) else job['descriptor'])
            async def load():
                async with self.service.source_slots['maps']:
                    return await self.service.maps_web.prices(query)
            async with asyncio.timeout(60):
                await self.cache.get('maps','maps:'+query.model_dump_json(),load,wait_refresh=True)
            success = True
            return True
        finally:
            acquisition_purpose.reset(purpose)
            background_acquisition.reset(token)
            await self.cache._db('finish_inventory_patrol', job, owner, success)

    async def run(self):
        while True:
            await asyncio.sleep(60)
            try:
                await self.step()
            except Exception:
                logger.warning('Inventory patrol deferred')
