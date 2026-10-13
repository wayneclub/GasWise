"""Run inside the deployed backend; no credentials or query keys are printed.

Makes three bounded searches in public DTLA, without routes, details or lookups.
Also checks shared background budgets using isolated temporary source counters.
"""

import asyncio
import json
import uuid
from time import perf_counter

import httpx

from gaswise.app.settings import Settings
from gaswise.domain.ports import ProviderError
from gaswise.providers.storage.postgres import PostgresPricingCache


async def verify_budget(store):
    source = "pilot_test_" + uuid.uuid4().hex
    try:
        async def charge():
            try:
                await store.consume(source, 10, background=True, background_daily_limit=3)
                return True
            except ProviderError:
                return False

        assert sum(await asyncio.gather(*(charge() for _ in range(6)))) == 2
        await store.consume(source, 10)
        await store.pool.execute("UPDATE gaswise.source_limits SET window_start=now()-interval '61 seconds' WHERE source=$1", source)
        assert await charge()
        assert not await charge()
        assert (await store.budget_state(source))["background_day_used"] == 3
        await store.consume(source, 10)
        return {"shared_background_minute_cap": True, "shared_background_daily_cap": True,
                "foreground_capacity_preserved": True}
    finally:
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1", source)


async def main():
    settings = Settings()
    store = await PostgresPricingCache.connect(settings.database_url.get_secret_value())
    try:
        budget = await verify_budget(store)
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=90,
                                    headers={"Authorization": "Bearer " + settings.api_token.get_secret_value()}) as client:
            status = await client.get("/v1/sources/refresh-status")
            status.raise_for_status()
            assert status.json()["enabled"]
            searches = []
            original_reports = None
            for gallons in (8, 9, 10):
                started = perf_counter()
                response = await client.post("/v1/smart/search", json={
                    "origin": {"lat": 34.03938, "lng": -118.2663},
                    "radius_meters": 2000, "fuel_type": "premium", "payment_type": "credit",
                    "gallons": gallons, "calculate_routes": False, "discovery_tiles": 1,
                    "maps_detail_limit": 0, "gasbuddy_page_limit": 1, "station_lookup_limit": 0,
                })
                response.raise_for_status()
                result = response.json()
                reports = sorted((quote["source"], quote["id"], quote.get("price_updated_at"), quote["fetched_at"])
                                 for quote in result["snapshot"]["stations"])
                if original_reports is None:
                    original_reports = reports
                elif reports != original_reports:
                    raise AssertionError("Repeated search changed original observation timestamps")
                searches.append({"elapsed_seconds": round(perf_counter() - started, 2),
                                 "cache_hits": result["cache_hits"], "upstream_calls": result["upstream_calls"],
                                 "quote_count": len(reports), "sources": result["snapshot"]["source_statuses"]})
            status = await client.get("/v1/sources/refresh-status")
            status.raise_for_status()
            print(json.dumps({"budget_checks": budget, "searches": searches,
                              "unchanged_observation_times": True, "refresh_status": status.json()}, indent=2))
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
