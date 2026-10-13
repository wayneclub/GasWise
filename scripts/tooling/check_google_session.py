"""Run inside the backend container; one budgeted check, no cookies in output."""
import asyncio
import json

import httpx

from gaswise.app.settings import Settings
from gaswise.contracts.sources import MapsWebSearch
from gaswise.providers.google.maps_web import MapsWebProvider
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.providers.storage.request_budget import RequestBudget


async def check():
    settings = Settings()
    store = await PostgresPricingCache.connect(settings.database_url.get_secret_value())
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            provider = MapsWebProvider(client, settings.maps_web_session_file)
            provider.request_budget = RequestBudget(store, {"maps": settings.maps_requests_per_minute})
            # One search, zero detail calls. The website's minimal place endpoint can
            # omit field 86 even while region search supplies authenticated full tables.
            data = await provider.prices(MapsWebSearch(
                origin={"lat": 34.0390107, "lng": -118.2672801}, radius_meters=9000,
                fuel_type="premium", detail_limit=0,
            ))
            healthy = any(quote.fuel_type != "regular" for quote in data.all_prices)
            print(json.dumps({"status": "full_fuel_table_available" if healthy else "session_or_canary_needs_check"}))
            return 0 if healthy else 2
    finally:
        await store.close()


if __name__ == "__main__":
    try:
        code = asyncio.run(check())
    except Exception:
        print('{"status":"session_check_deferred"}')
        code = 3
    raise SystemExit(code)
