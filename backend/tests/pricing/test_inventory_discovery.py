import copy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from gaswise.contracts.common import Point, Station
from gaswise.contracts.smart import SmartSearch
from gaswise.contracts.sources import MapsWebPrices, MapsWebStation
from gaswise.domain.pricing.cells import Coverage
from gaswise.services.pricing.discovery import acquire, discover_maps
from gaswise.services.pricing.smart import SmartService

ORIGIN = Point(lat=34, lng=-118)


class Catalog:
    def __init__(self, rows):
        self.rows, self.cache = rows, {}

    async def close(self):
        pass

    async def nearby_inventory(self, origin, radius):
        return self.rows

    async def get(self, source, key, operation):
        if key in self.cache:
            return copy.deepcopy(self.cache[key]), True
        value = await operation()
        self.cache[key] = copy.deepcopy(value)
        return value, False


def known(identifier, source='google_maps_web', lat=34):
    return dict(source=source, station_id=f'google_maps_web:{identifier}' if source=='google_maps_web' else identifier,
                canonical_id=f'google_places:{identifier}' if source=='google_maps_web' else None,
                name=identifier, address=None, location={'lat':lat, 'lng':-118}, last_seen_at='2026-10-20T12:00:00Z')


def inventory(identifier):
    return MapsWebStation(place_id=identifier, name=identifier, location=ORIGIN,
                          distance_meters=0, available_fuel_types=[])


def test_known_missing_station_reopens_estimated_covered_cells_without_repeating_queries():
    coverage = Coverage(ORIGIN, 2000)
    coverage.remember([dict(place_id='missing', location=ORIGIN.model_dump())])
    coverage.record(ORIGIN, 5000, 3, 3, 100, 20)
    points, _ = coverage.wave(1)
    assert len(points) == 1
    coverage.observed(['missing'])
    assert coverage.wave(1)[0] == []


async def test_catalog_keeps_missing_station_without_inventing_a_price_or_live_observation():
    maps = SimpleNamespace(prices=AsyncMock(return_value=MapsWebPrices(
        stations=[], inventory=[inventory('found')], warnings=[], candidate_count=1)))
    service = SmartService(b'test', 'prices_only', maps_web=maps,
                           shared_cache=Catalog([known('found'), known('missing')]))
    query = SmartSearch(origin=ORIGIN, discovery_tiles=1)
    outcomes, _ = await discover_maps(service, query, query)
    result = outcomes[0][0]
    assert maps.prices.call_count == 1 and not result.all_prices and not result.stations
    missing = next(row for row in result.inventory if row.place_id=='missing')
    assert missing.discovery_state=='known' and missing.last_seen_at is not None
    assert missing.open_now is None and not missing.available_fuel_types
    assert result.discovery_metrics['maps_observed_stations']==1
    assert result.discovery_metrics['maps_known_missing']==1
    await service.close()


async def test_maps_search_cards_are_shared_across_grades_without_extra_source_calls():
    now = datetime.now(UTC)
    rows = [Station(id='a', source='google_maps_web', name='a', location=ORIGIN,
                    fuel_type=fuel, price_per_gallon=price, fetched_at=now)
            for fuel, price in [('regular','4.00'),('premium','4.50')]]
    maps = SimpleNamespace(prices=AsyncMock(return_value=MapsWebPrices(
        all_prices=rows, stations=[rows[0]], inventory=[inventory('a')], warnings=[], candidate_count=1)))
    service = SmartService(b'test', 'prices_only', maps_web=maps)
    for fuel in ('regular','premium'):
        query = SmartSearch(origin=ORIGIN, fuel_type=fuel, maps_detail_limit=0, discovery_tiles=1)
        outcomes, _ = await discover_maps(service, query, query)
        assert [row.fuel_type for row in outcomes[0][0].stations] == [fuel]
    assert maps.prices.call_count == 1
    await service.close()


async def test_waze_missing_catalog_stations_use_one_shared_area_query_per_cell():
    class Waze:
        calls = 0
        async def stations(self, query, *, all_fuels=False):
            self.calls += 1
            identifier = 'first' if self.calls==1 else 'missing'
            return [Station(id=identifier, source='waze', name=identifier, location=ORIGIN,
                            fuel_type=fuel, price_per_gallon='4.50', fetched_at=datetime.now(UTC))
                    for fuel in ('regular','premium')]
    provider = Waze()
    service = SmartService(b'test', 'prices_only', waze=provider,
                           shared_cache=Catalog([known('missing','waze',34.02), known('another','waze',34.02)]))
    for fuel in ('regular','premium'):
        query = SmartSearch(origin=ORIGIN, fuel_type=fuel, discovery_tiles=8)
        result = await acquire(service, query, query)
        assert {row.id for row in result['waze'][0]} == {'first','missing'}
    assert provider.calls == 2
    assert result['_waze_metrics']['waze_searches'] == 0
    await service.close()
