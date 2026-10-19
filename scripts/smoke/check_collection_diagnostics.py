"""Check diagnostic ownership and retention with an isolated DB job; no provider IO."""
import asyncio
import json
import uuid

from gaswise.app.settings import Settings
from gaswise.providers.storage.postgres import PostgresPricingCache


async def main():
    store = await PostgresPricingCache.connect(Settings().database_url.get_secret_value())
    job = 'diagnostic_canary_' + uuid.uuid4().hex
    try:
        await store.pool.execute("""INSERT INTO gaswise.base_collection_jobs
            (id,base,source,fuel,descriptor,lease_owner) VALUES($1,'canary','canary','regular','{}','owner')""", job)
        await store.record_base_failure_diagnostic(job, 'other_owner', 'gasbuddy_http_schema_changed')
        assert await store.pool.fetchval('SELECT last_failure_code FROM gaswise.base_collection_jobs WHERE id=$1', job) is None
        await store.record_base_failure_diagnostic(job, 'owner', 'gasbuddy_http_schema_changed')
        await store.finish_base_job(job, 'owner', 86400, None, 1, 1)
        row = await store.pool.fetchrow('SELECT last_failure_code,last_failure_at,last_error FROM gaswise.base_collection_jobs WHERE id=$1', job)
        assert row['last_failure_code'] == 'gasbuddy_http_schema_changed'
        assert row['last_failure_at'] is not None and row['last_error'] is None
        print(json.dumps({'lease_owner_guard': True, 'diagnostic_retained_after_recovery': True, 'provider_http_requests': 0}))
    finally:
        await store.pool.execute('DELETE FROM gaswise.base_collection_jobs WHERE id=$1', job)
        await store.close()


if __name__ == '__main__':
    asyncio.run(main())
