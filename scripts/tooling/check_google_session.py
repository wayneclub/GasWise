"""Run inside the backend container; one budgeted check, no cookies in output."""
import asyncio
import json

import httpx

from gaswise.app.settings import Settings
from gaswise.providers.google.maps_web import DETAIL_FEATURES, MapsWebProvider, records
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.providers.storage.request_budget import RequestBudget


async def check():
    settings = Settings()
    store = await PostgresPricingCache.connect(settings.database_url.get_secret_value())
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            provider = MapsWebProvider(client, settings.maps_web_session_file)
            provider.request_budget = RequestBudget(store, {"maps": settings.maps_requests_per_minute})
            # Known public canary with a browser-verified full fuel table; this is a
            # session health check, never a substitute for user-region price acquisition.
            pb = "!1m6!1s0x80c2c7cfc7d0f519:0x62b7eab7cbae63d2!3m1!1d1000!4m2!3d34.0336356!4d-118.2622718!3m1!1e3" + DETAIL_FEATURES
            data = await provider.get_data("/maps/preview/place", {
                "authuser": "0", "hl": "en", "gl": "us", "q": "Chevron", "pb": pb,
            }, provider.headers())
            target = [row for row in records(data) if row[78] == "ChIJGfXQx8_HwoAR0mOuy7fqt2I"]
            healthy = bool(target and target[0][86])
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
