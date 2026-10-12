import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

from gaswise.contracts.common import Point
from gaswise.contracts.search import RankOptions
from gaswise.contracts.smart import SmartRerank, SmartSearch
from gaswise.providers.pricing.aaa import AAASnapshot, RegionAverage
from gaswise.services.pricing.regional import benchmarks, match_benchmark
from gaswise.services.pricing.smart import SmartService
from tests.support.smart import CountingProvider


async def test_three_distinct_leaders_per_category_reuse_same_signed_quotes():
    provider = CountingProvider()
    service = SmartService(b'test', 'demo', demo=provider)
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), mpg='25', calculate_routes=True, time_value_per_hour=15))
    for category in ('cheapest_overall', 'best_value', 'fastest_stop'):
        board = result.ranking.leaderboards[category]
        assert len(board) == 3
        assert len({r.price_comparison.station_key for r in board}) == 3
        assert board[0].station.id == result.ranking.recommendations[category].station.id
    money = result.ranking.leaderboards['cheapest_overall']
    fast = result.ranking.leaderboards['fastest_stop']
    assert [r.actual_fuel_cost for r in money] == sorted(r.actual_fuel_cost for r in money)
    assert [r.extra_travel_minutes for r in fast] == sorted(r.extra_travel_minutes for r in fast)
    before = provider.routes
    changed = await service.rerank(SmartRerank(snapshot=result.snapshot, signature=result.signature, options=RankOptions(time_value_per_hour=100)))
    assert provider.routes == before
    assert not any(changed.upstream_calls.values())
    assert changed.ranking.leaderboards['cheapest_overall'][0].station.id == result.ranking.leaderboards['cheapest_overall'][0].station.id
    assert changed.ranking.leaderboards['fastest_stop'][0].station.id == result.ranking.leaderboards['fastest_stop'][0].station.id
    await service.close()


def test_aaa_matches_grade_and_explicit_metro_else_labeled_state():
    snapshot = AAASnapshot(state='CA', source_url='https://gasprices.aaa.com/?state=CA', price_as_of=date(2026,10,12), retrieved_at=datetime.now(UTC), county_status='unavailable', regions=[
        RegionAverage(name='California', level='state', prices={'current':{'premium':Decimal('6.01'), 'mid_grade':Decimal('5.51')}}),
        RegionAverage(name='Los Angeles-Long Beach', level='metro', prices={'current':{'premium':Decimal('6.11'), 'mid_grade':Decimal('5.61')}}),
    ])
    from types import SimpleNamespace
    station = SimpleNamespace(details={}, address='1400 S Alameda St, Los Angeles, CA 90021-2426', fuel_type='premium')
    average = match_benchmark(station, benchmarks(snapshot, 'premium'))
    assert average.scope == 'metro' and average.region == 'Los Angeles-Long Beach'
    assert average.price_per_gallon == Decimal('6.11')
    station.address = '1 Main St, Unknown City, CA 90015'
    assert match_benchmark(station, benchmarks(snapshot, 'premium')).scope == 'state'
    station.address = '1 Main St, Los Angeles, NV 90015'
    assert match_benchmark(station, benchmarks(snapshot, 'premium')) is None
    station.address, station.fuel_type = '1 Main St, Long Beach, CA 90802', 'midgrade'
    assert match_benchmark(station, benchmarks(snapshot, 'midgrade')).price_per_gallon == Decimal('5.61')


async def test_routes_overlap_but_global_concurrency_is_bounded_for_many_users():
    class Routes(CountingProvider):
        active = 0
        peak = 0
        async def route(self, *args):
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                await asyncio.sleep(.02)
                return await super().route(*args)
            finally:
                self.active -= 1
    provider = Routes()
    service = SmartService(b'test', 'demo', demo=provider)
    result = await asyncio.gather(*(service.search(SmartSearch(origin=Point(lat=34, lng=-118), mpg='25', gallons=10+i, calculate_routes=True)) for i in range(24)))
    assert 1 < provider.peak <= 4
    assert provider.routes == 4
    assert all(len(r.ranking.results) == 4 for r in result)
    assert sum(r.upstream_calls['routes'] for r in result) == 0  # synthetic routes incur no live quota
    await service.close()


def test_shared_viewport_covers_original_circle_and_keeps_routes_exact():
    from gaswise.domain.pricing.comparison import distance_meters
    from gaswise.services.pricing.discovery import shared_viewport
    point = Point(lat=34.0390107, lng=-118.2672801)
    centre, radius = shared_viewport(point, 8000)
    assert distance_meters(point, centre) + 8000 <= radius
    neighbour = Point(lat=point.lat + .00001, lng=point.lng + .00001)
    assert shared_viewport(neighbour, 8000) == (centre, radius)
    assert shared_viewport(point, 50000) == (point, 50000)


async def test_aaa_failure_is_isolated_and_cooldown_counts_actual_operations():
    from gaswise.domain.ports import ProviderError
    from tests.support.smart import MapsInventory, RawGasBuddy
    class UnavailableAAA:
        calls = 0
        async def averages(self, state):
            self.calls += 1
            raise ProviderError('aaa_upstream_unavailable')
    aaa = UnavailableAAA()
    service = SmartService(b'test', 'prices_only', maps_web=MapsInventory(), gasbuddy=RawGasBuddy(), router=CountingProvider(), aaa=aaa)
    query = SmartSearch(origin=Point(lat=34,lng=-118), mpg='25', calculate_routes=True)
    first = await service.search(query)
    second = await service.search(query)
    assert first.ranking.results and second.ranking.results
    assert aaa.calls == first.upstream_calls['aaa_averages'] == 1
    assert second.upstream_calls['aaa_averages'] == 0
    assert second.snapshot.regional_averages == []
    assert any('AAA regional average unavailable' in text for text in second.snapshot.warnings)
    await service.close()
