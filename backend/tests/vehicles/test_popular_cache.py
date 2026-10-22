from gaswise.services.vehicles.popular_cache import POPULAR_VEHICLE_IDS, warm_popular_vehicle_records


async def test_market_validated_records_warm_concurrently_and_isolate_failures():
    class Provider:
        def __init__(self):
            self.calls = []

        async def vehicle(self, vehicle_id):
            self.calls.append(vehicle_id)
            if vehicle_id == POPULAR_VEHICLE_IDS[1]:
                raise RuntimeError("temporary EPA failure")

    provider = Provider()
    results = await warm_popular_vehicle_records(provider)

    assert len(POPULAR_VEHICLE_IDS) == 59
    assert len(set(POPULAR_VEHICLE_IDS)) == 59
    assert set(provider.calls) == set(POPULAR_VEHICLE_IDS)
    assert results.count(True) == 58
    assert results.count(False) == 1
