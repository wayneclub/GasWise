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


def test_offline_secondary_falls_back_before_http_and_query_remains_pinned(tmp_path):
    import json

    from gaswise.providers.http.egress_pool import selected_lane
    path = tmp_path / 'health.json'
    key = keys_for_lanes()[1]
    token = collection_egress_key.set(key)
    try:
        path.write_text(json.dumps({'unavailable_lanes': []}))
        assert selected_lane(2, path) == 1
        path.write_text(json.dumps({'unavailable_lanes': [1]}))
        assert selected_lane(2, path) == 1  # Never switch a query's pages between exits.
    finally:
        collection_egress_key.reset(token)
    for i in range(100, 300):
        token = collection_egress_key.set(str(i))
        try:
            if lane_index(2) == 1:
                assert selected_lane(2, path) == 0
                break
        finally:
            collection_egress_key.reset(token)
    else:
        raise AssertionError('No secondary lane sample found')


def test_missing_or_stale_heartbeat_keeps_new_queries_on_primary(tmp_path):
    import os
    import time

    from gaswise.providers.http.egress_pool import selected_lane
    path = tmp_path / 'missing.json'
    token = collection_egress_key.set(keys_for_lanes()[1])
    try:
        assert selected_lane(2, path) == 0
        stale = tmp_path / 'stale.json'
        stale.write_text('{"unavailable_lanes": []}')
        os.utime(stale, (time.time() - 90, time.time() - 90))
        assert selected_lane(2, stale) == 0
    finally:
        collection_egress_key.reset(token)


def test_no_available_lane_defers_as_a_source_failure(tmp_path):
    import json

    from gaswise.providers.http.egress_pool import selected_lane
    path = tmp_path / 'health.json'
    path.write_text(json.dumps({'unavailable_lanes': [0, 1]}))
    token = collection_egress_key.set(keys_for_lanes()[0])
    try:
        # Every lane is offline: the source defers instead of raising a
        # programming error that the API would report as an unhandled 500.
        with pytest.raises(ProviderError, match='^pricing_egress_unavailable$'):
            selected_lane(2, path)
    finally:
        collection_egress_key.reset(token)
