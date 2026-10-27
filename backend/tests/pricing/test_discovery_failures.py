import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.smart import SmartSearch
from gaswise.domain.ports import ProviderError
from gaswise.services.pricing.discovery import discover_maps
from gaswise.services.pricing.smart import SmartService


@pytest.mark.parametrize('reason', ['google_maps_web_unavailable', 'google_maps_web_session_expired',
                                    'google_maps_web_session_rejected', 'pricing_egress_unavailable'])
async def test_failed_first_maps_wave_does_not_expand_into_more_failing_requests(reason):
    class BrokenMaps:
        calls = 0

        async def prices(self, query):
            self.calls += 1
            raise ProviderError(reason)

    provider = BrokenMaps()
    service = SmartService(b'test', 'prices_only', maps_web=provider)
    query = SmartSearch(origin=Point(lat=34, lng=-118), discovery_tiles=20)
    if reason == 'pricing_egress_unavailable':
        with pytest.raises(ProviderError, match=reason):
            await discover_maps(service, query, query)
    else:
        outcomes, _ = await discover_maps(service, query, query)
        assert len(outcomes) == 1
        assert str(outcomes[0]) == reason
    assert provider.calls == 1
    await service.close()


async def test_later_failed_wave_retains_earlier_success_and_coverage(monkeypatch):
    from gaswise.services.pricing import discovery

    class Coverage:
        def __init__(self, *args):
            pass

        def record(self, *args):
            pass

        def wave(self, *args):
            return [Point(lat=34.01, lng=-118), Point(lat=34.02, lng=-118)], 1000

        def fraction(self):
            return 0.4

    monkeypatch.setattr(discovery, 'Coverage', Coverage)
    from gaswise.contracts.sources import MapsWebPrices, MapsWebStation
    successful = MapsWebPrices(candidate_count=20, inventory=[MapsWebStation(
        place_id='observed-station', name='Fixture', location=Point(lat=34,lng=-118),
        distance_meters=0, available_fuel_types=[])], stations=[], warnings=[], candidate_reach_meters=100)

    class Maps:
        calls = 0

        async def prices(self, query):
            self.calls += 1
            if self.calls == 1:
                return successful
            raise ProviderError('google_maps_web_unavailable')

    provider = Maps()
    service = SmartService(b'test', 'prices_only', maps_web=provider)
    query = SmartSearch(origin=Point(lat=34, lng=-118), discovery_tiles=20)
    outcomes, covered = await discover_maps(service, query, query)
    assert len(outcomes) == provider.calls == 3
    assert outcomes[0][0].inventory[0].place_id == 'observed-station'
    assert covered == 0.4
    assert all(isinstance(row, ProviderError) for row in outcomes[1:])
    await service.close()
