"""Isolated DB scheduling and reservation checks; never contacts providers."""
import asyncio
import json
import uuid

from gaswise.app.settings import Settings
from gaswise.domain.ports import ProviderError
from gaswise.providers.storage.postgres import PostgresPricingCache


async def main():
    store = await PostgresPricingCache.connect(Settings().database_url.get_secret_value())
    source = "rotation_canary_" + uuid.uuid4().hex
    ids = [source + suffix for suffix in (":la", ":large", ":waiting")]
    try:
        for job_id, population, mandatory, hours in zip(ids, (1, 1000000, 1), (True, False, False), (1, 1, 100), strict=True):
            await store.pool.execute("""INSERT INTO gaswise.base_collection_jobs
                (id,base,source,fuel,descriptor,population_priority,mandatory,request_reserve,next_due)
                VALUES($1,$1,$2,'regular','{}',$3,$4,4,now()-$5*interval '1 hour')""",
                job_id, source, population, mandatory, float(hours))
        assert await store.claim_base_job("canary", [source]) == ids[0]
        await store.configure_daily_ramp([source], 10, 1, 20)
        await store.pool.execute("UPDATE gaswise.source_limits SET background_day_count=6 WHERE source=$1", source)
        try:
            await store.consume(source, 100, background=True)
            raise AssertionError("Optional request spent reserved allowance")
        except ProviderError as error:
            assert str(error) == source + "_mandatory_budget_reserved"
        await store.consume(source, 100, background=True, mandatory=True)
        await store.finish_base_job(ids[0], "canary", 86400, None, 1, 1)
        assert await store.claim_base_job("canary", [source]) == ids[2]
        await store.consume(source, 100, background=True)
        status = {row["id"]: row for row in await store.base_job_status() if row["source"] == source}
        assert status[ids[0]]["mandatory"] and status[ids[2]]["priority_score"] > status[ids[1]]["priority_score"]
        print(json.dumps({"mandatory_first": True, "aging_prevents_starvation": True,
                          "reserved_budget_enforced": True, "reservation_released_on_success": True,
                          "provider_http_requests": 0}))
    finally:
        await store.pool.execute("DELETE FROM gaswise.base_collection_jobs WHERE source=$1", source)
        await store.pool.execute("DELETE FROM gaswise.source_limits WHERE source=$1", source)
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
