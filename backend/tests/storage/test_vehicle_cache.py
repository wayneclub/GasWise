import json
from datetime import UTC, datetime
from types import SimpleNamespace

from gaswise.providers.storage.postgres import PostgresPricingCache


async def test_postgres_vehicle_cache_reads_json_and_upserts_public_reference_record():
    class Pool:
        def __init__(self):
            self.execute_args = None

        async def fetchval(self, query, vehicle_id):
            assert "refresh_after>now()" in query
            assert vehicle_id == 123
            return json.dumps({"id": 123, "source": "fueleconomy_gov"})

        async def execute(self, query, *args):
            assert "ON CONFLICT(vehicle_id) DO UPDATE" in query
            self.execute_args = args

    pool = Pool()
    store = PostgresPricingCache(pool)
    assert await store.read_vehicle(123) == {"id": 123, "source": "fueleconomy_gov"}

    now = datetime.now(UTC)
    vehicle = SimpleNamespace(
        id=123,
        source="fueleconomy_gov",
        year=2025,
        make="Fixture",
        model="Car",
        fetched_at=now,
        model_dump=lambda mode: {"id": 123, "source": "fueleconomy_gov"},
    )
    await store.write_vehicle(vehicle)

    assert pool.execute_args[:5] == (123, "fueleconomy_gov", 2025, "Fixture", "Car")
    assert json.loads(pool.execute_args[5]) == {"id": 123, "source": "fueleconomy_gov"}
    assert pool.execute_args[6:] == (now, 30)
