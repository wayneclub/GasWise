import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gaswise.contracts.sources import MapsWebPrices
from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.services.pricing.inventory_patrol import InventoryPatrol


def setup():
    job = dict(source='maps',cell_id='test',radius_meters=800,
               descriptor={'origin':{'lat':34,'lng':-118},'radius_meters':800})
    cache = SimpleNamespace(budget_state=AsyncMock(return_value={'used':0,'background_day_used':0}),
                            _db=AsyncMock(return_value=job))
    async def get(source,key,load,**kwargs):
        assert background_acquisition.get() and kwargs['wait_refresh']
        return await load(),False
    cache.get=get
    provider=SimpleNamespace(prices=AsyncMock(return_value=MapsWebPrices(stations=[],inventory=[],warnings=[])))
    service=SimpleNamespace(shared_cache=cache,maps_web=provider,source_slots={'maps':asyncio.Semaphore(1)})
    return InventoryPatrol(service),cache,provider


async def test_optional_budget_is_checked_before_claiming_patrol_work():
    patrol,cache,provider=setup()
    cache.budget_state.return_value['background_usage']={'demand':20}
    assert not await patrol.step()
    cache._db.assert_not_called()
    provider.prices.assert_not_called()


async def test_patrol_uses_area_cache_and_releases_owner_on_success():
    patrol,cache,provider=setup()
    assert await patrol.step()
    assert provider.prices.call_count==1
    assert cache._db.call_args.args[0]=='finish_inventory_patrol'
    assert cache._db.call_args.args[-1] is True
    assert not background_acquisition.get()


async def test_cancellation_releases_patrol_and_restores_foreground_context():
    patrol,cache,provider=setup()
    started=asyncio.Event()
    async def wait(query):
        started.set()
        await asyncio.Event().wait()
    provider.prices.side_effect=wait
    task=asyncio.create_task(patrol.step())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cache._db.call_args.args[-1] is False
    assert not background_acquisition.get()
