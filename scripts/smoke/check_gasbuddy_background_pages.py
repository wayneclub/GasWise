"""One real, budgeted three-page GasBuddy canary on the production host.

Requires operator authorization. No route/Maps/Waze calls; prints counts only.
The default public city query may stop early if the source has no next page.
"""

import asyncio
import json
from time import perf_counter

from gaswise.app.bootstrap import build_services
from gaswise.app.runtime import ProviderOverrides
from gaswise.app.settings import Settings
from gaswise.contracts.sources import GasBuddySearch
from gaswise.domain.pricing.shared_cache import background_acquisition


async def main():
    settings = Settings(hot_pricing_refresh_enabled=False, top_tier_refresh_enabled=False)
    async with build_services(settings, ProviderOverrides()) as services:
        before = await services.smart.shared_cache.budget_state("gasbuddy")
        if before["blocked_seconds"] or before["background_day_used"] > (before.get("daily_limit") or settings.hot_pricing_refresh_daily_requests) - 4:
            raise SystemExit("Canary deferred: source cooldown or insufficient daily background budget")
        query = GasBuddySearch(search="Los Angeles, CA", max_pages=3, max_results=100,
                               include_payment_variants=True, payment_type="cash_or_credit")
        started = perf_counter()
        token = background_acquisition.set(True)
        try:
            result = await services.gasbuddy_web.prices(query)
        finally:
            background_acquisition.reset(token)
        after = await services.smart.shared_cache.budget_state("gasbuddy")
        print(json.dumps({
            "elapsed_seconds": round(perf_counter() - started, 2),
            "page_requests": result.page_requests,
            "quote_records": len(result.prices),
            "distinct_source_station_ids": len({quote.id for quote in result.prices}),
            "background_http_charged": after["background_day_used"] - before["background_day_used"],
            "background_daily_used": after["background_day_used"],
            "background_daily_limit": after.get("daily_limit") or settings.hot_pricing_refresh_daily_requests,
            "partial": result.partial,
            "evidence": "one live city query; station updates are not unique daily city coverage",
        }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
