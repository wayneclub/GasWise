from types import SimpleNamespace

import httpx
import pytest

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.collection_errors import safe_failure_code
from gaswise.domain.pricing.shared_cache import collection_egress_key
from gaswise.providers.http.egress_pool import PooledGasBuddySession, PooledHTTPClient, lane_index


def keys_for_lanes():
    keys = {}
    for i in range(100):
        token = collection_egress_key.set(str(i))
        try:
            keys.setdefault(lane_index(2), str(i))
        finally:
            collection_egress_key.reset(token)
    assert len(keys) == 2
    return keys


async def test_pinned_exit_cookie_jars_provider_headers_and_no_status_failover():
    made = []
    class Client:
        def __init__(self, proxy):
            self.proxy, self.calls, self.cookies = proxy, [], {}
            self.closed = False
        async def get(self, url, **kwargs):
            self.calls.append(kwargs)
            self.cookies['node_cookie'] = self.proxy
            return SimpleNamespace(status_code=429)
        async def post(self, url, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(status_code=200)
        async def aclose(self):
            self.closed = True
    def factory(proxy):
        client = Client(proxy)
        made.append(client)
        return client
    pool = PooledHTTPClient(['http://node-a:8888', 'http://node-b:8888'], client_factory=factory)
    keys = keys_for_lanes()
    for index, key in keys.items():
        token = collection_egress_key.set(key)
        try:
            result = await pool.get('https://example.com', headers={'User-Agent': 'authorized-app', 'Cookie': 'private'})
            assert result.status_code == 429  # Delivered unchanged; never retry on another node.
            await pool.post('https://example.com', headers={'User-Agent': 'authorized-app'})
            assert len(made[index].calls) == 2
            assert made[index].calls[0]['headers']['User-Agent'] == 'authorized-app'
        finally:
            collection_egress_key.reset(token)
    assert made[0].cookies != made[1].cookies
    await pool.aclose()
    assert all(client.closed for client in made)


async def test_gasbuddy_csrf_workers_are_pinned_and_share_one_budget():
    class Worker:
        def __init__(self, session_seconds, client_factory):
            self.client = client_factory()
            self.calls = 0
        async def snapshot(self, query, url, fuel):
            self.calls += 1
            assert self.request_budget is budget
            return self.client.proxy, self.client.profile
        async def close(self):
            await self.client.aclose()
    budget = object()
    pool = PooledGasBuddySession(['http://node-a:8888', 'http://node-b:8888'], worker_factory=Worker)
    pool.request_budget = budget
    for index, key in keys_for_lanes().items():
        token = collection_egress_key.set(key)
        try:
            first = await pool.snapshot(None, '', 1)
            assert await pool.snapshot(None, '', 1) == first
            assert pool.workers[index].calls == 2
        finally:
            collection_egress_key.reset(token)
    assert pool.workers[0].client.profile != pool.workers[1].client.profile
    await pool.close()


@pytest.mark.parametrize('error,code', [
    (ProviderError('gasbuddy_http_schema_changed'), 'gasbuddy_http_schema_changed'),
    (ProviderError('token=private cookie=secret'), 'unclassified'),
    (httpx.ReadTimeout('private upstream URL'), 'unclassified'),
    (ValueError('private response body'), 'ValueError'),
])
def test_failure_diagnostics_never_persist_raw_messages(error, code):
    assert safe_failure_code(error) == code
