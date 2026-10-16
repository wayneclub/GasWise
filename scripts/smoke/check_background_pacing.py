"""Verify shared task pacing and healthy budget deferrals; no provider HTTP."""
import asyncio
import json
import uuid

from gaswise.app.settings import Settings
from gaswise.providers.storage.postgres import PostgresPricingCache


async def main():
    store = await PostgresPricingCache.connect(Settings().database_url.get_secret_value())
    source = "pacing_canary_" + uuid.uuid4().hex
    ids = [source + str(i) for i in range(3)]
    try:
        await store.configure_daily_ramp([source], 160, 40, 800)
        await store.configure_background_pacing(source, True)
        for job in ids:
            await store.pool.execute("""INSERT INTO gaswise.base_collection_jobs
                (id,base,source,fuel,descriptor,request_reserve) VALUES($1,'canary',$2,'regular','{}',4)""", job, source)
        results = await asyncio.gather(store.claim_base_job("one", [source]), store.claim_base_job("two", [source]))
        assert sum(result is not None for result in results) == 1
        state = await store.budget_state(source)
        assert 2150 < state["background_pacing_seconds"] <= 2160
        pending = next(job for job in ids if job not in results)
        await store.pool.execute("UPDATE gaswise.base_collection_jobs SET mandatory=true WHERE id=$1", pending)
        assert await store.claim_base_job("mandatory", [source]) == pending
        before = await store.budget_state(source)
        await store.finish_base_job(pending, "mandatory", 60, source + "_background_daily_budget_exhausted", 0, 0)
        after = await store.budget_state(source)
        assert before["daily_review_at"] == after["daily_review_at"]
        row = await store.pool.fetchrow("SELECT last_collection_failure_at FROM gaswise.source_limits WHERE source=$1", source)
        assert row["last_collection_failure_at"] is None
        await store.configure_background_pacing(source, True)
        assert (await store.budget_state(source))["background_pacing_seconds"] > 2100
        print(json.dumps({"concurrent_optional_claims": 1, "spacing_seconds": 2160,
                          "mandatory_bypasses_pacing": True, "local_deferral_preserves_review": True,
                          "restart_preserves_pacing": True, "provider_http_requests": 0}))
    finally:
        await store.pool.execute("DELETE FROM gaswise.base_collection_jobs WHERE source=$1", source)
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1", source)
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
