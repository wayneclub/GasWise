"""Exercise adaptive budgets using isolated production DB counters; zero provider HTTP."""

import asyncio
import json
import uuid

from gaswise.app.settings import Settings
from gaswise.providers.storage.postgres import PostgresPricingCache


async def main():
    store = await PostgresPricingCache.connect(Settings().database_url.get_secret_value())
    other = await PostgresPricingCache.connect(Settings().database_url.get_secret_value())
    source = "ramp_canary_" + uuid.uuid4().hex
    try:
        await store.configure_daily_ramp([source], 80, 40, 800)
        await store.pool.execute("""UPDATE gaswise.source_limits SET daily_review_at=now()-interval '25 hours',
            daily_review_requests=80,background_last_request_at=now(),background_day_count=80 WHERE source=$1""", source)
        await asyncio.gather(store.budget_state(source), other.budget_state(source))
        assert (await store.budget_state(source))["daily_limit"] == 160
        assert (await store.budget_state(source))["background_day_used"] == 80
        await other.configure_daily_ramp([source], 80, 40, 800)
        assert (await store.budget_state(source))["daily_limit"] == 160
        await store.consume(source, 100, background=True, background_daily_limit=80)
        state = await store.budget_state(source)
        assert state["background_day_used"] == 81 and state["daily_review_requests"] == 1
        await other.cooldown(source, 120)
        assert (await store.budget_state(source))["daily_limit"] == 80
        await other.cooldown(source, 120)
        await other.cooldown(source, 120)
        assert (await store.budget_state(source))["daily_limit"] == 40
        assert (await store.budget_state(source))["background_day_used"] == 81
        print(json.dumps({"single_step_concurrent_review": True, "restart_preserves_limit": True,
                          "usage_not_reset": True, "new_review_counts_only_new_attempts": True,
                          "rejection_halves_with_floor": True, "provider_http_requests": 0}))
    finally:
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1", source)
        await other.close()
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
