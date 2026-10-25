import asyncio
from datetime import UTC, datetime

from gaswise.contracts.common import Point, Station
from gaswise.contracts.smart import SmartSearch
from gaswise.services.pricing.discovery import acquire
from gaswise.services.pricing.smart import SmartService


class AllFuels:
    def __init__(self):
        self.calls = 0

    async def stations(self, query, *, all_fuels=False):
        self.calls += 1
        await asyncio.sleep(0)
        now = datetime.now(UTC)
        rows = [Station(id='w1', source='waze', name='Shell', location=query.origin,
                        fuel_type=fuel, price_per_gallon=price, fetched_at=now)
                for fuel, price in [('regular', '4.50'), ('premium', '4.90')]]
        return rows if all_fuels else [r for r in rows if r.fuel_type == query.fuel_type]


async def test_concurrent_and_later_grade_switches_share_one_waze_fetch():
    provider = AllFuels()
    service = SmartService(b'test', 'prices_only', waze=provider)
    regular = SmartSearch(origin=Point(lat=34, lng=-118), fuel_type='regular')
    premium = regular.model_copy(update={'fuel_type': 'premium'})
    a, b = await asyncio.gather(acquire(service, regular, regular), acquire(service, premium, premium))
    assert provider.calls == 1
    for result, fuel in [(a, 'regular'), (b, 'premium')]:
        rows, _ = result['waze']
        assert [r.fuel_type for r in rows] == [fuel]
    before = b['waze'][0][0].fetched_at
    again = await acquire(service, premium, premium)
    assert provider.calls == 1
    assert again['waze'][1]
    assert again['waze'][0][0].fetched_at == before
    assert not service.inflight
    await service.close()


async def test_foreground_uses_fixed_base_all_fuel_cache_key():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from gaswise.domain.pricing.collection_bases import BASES
    from gaswise.services.pricing.base_collection import collection_jobs

    provider = AllFuels()
    service = SmartService(b'test', 'prices_only', waze=provider)
    cache = SimpleNamespace(get=AsyncMock(return_value=([], True)))
    service.shared_cache = cache
    latitude, longitude = BASES['la']
    query = SmartSearch(origin=Point(lat=latitude, lng=longitude), radius_meters=10000)
    # Foreground includes a 20% soft-boundary margin; compare equal viewports.
    jobs = collection_jobs(SimpleNamespace(gasbuddy=None, maps_web=None, waze=provider), ['la'],
                           base_radius=12000)
    await acquire(service, query, query)
    assert cache.get.call_args.args[:2] == ('waze', next(iter(jobs.values())).raw_key)
    assert provider.calls == 0
    service.shared_cache = None
    await service.close()
