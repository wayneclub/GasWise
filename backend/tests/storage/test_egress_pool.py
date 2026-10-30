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


async def test_transport_failure_fails_over_in_flight_to_another_exit():
    class Worker:
        def __init__(self, session_seconds, client_factory):
            self.client = client_factory()
            self.fail = False
            self.calls = 0
        async def snapshot(self, query, url, fuel):
            self.calls += 1
            if self.fail:
                raise ProviderError('gasbuddy_http_unavailable')
            return self.client.proxy
        async def close(self):
            await self.client.aclose()
    pool = PooledGasBuddySession(['http://node-a:8888', 'http://node-b:8888'], worker_factory=Worker)
    pool.workers[1].fail = True
    token = collection_egress_key.set(keys_for_lanes()[1])
    try:
        # Fails over immediately in-flight on the same snapshot: no exception is raised to the caller.
        assert await pool.snapshot(None, '', 1) == 'http://node-a:8888'
        assert pool.workers[1].calls == 1
        assert pool.workers[0].calls == 1
        # Subsequent queries also skip the quarantined exit.
        assert await pool.snapshot(None, '', 1) == 'http://node-a:8888'
        assert pool.workers[1].calls == 1
        assert pool.workers[0].calls == 2
    finally:
        collection_egress_key.reset(token)
    await pool.close()


async def test_transport_failure_raises_when_all_lanes_fail():
    class Worker:
        def __init__(self, session_seconds, client_factory):
            self.client = client_factory()
        async def snapshot(self, query, url, fuel):
            raise ProviderError('gasbuddy_http_unavailable')
        async def close(self):
            await self.client.aclose()
    pool = PooledGasBuddySession(['http://node-a:8888', 'http://node-b:8888'], worker_factory=Worker)
    token = collection_egress_key.set(keys_for_lanes()[1])
    try:
        with pytest.raises(ProviderError, match='^gasbuddy_http_unavailable$'):
            await pool.snapshot(None, '', 1)
    finally:
        collection_egress_key.reset(token)
    await pool.close()


async def test_lane_quarantine_expires_and_only_follows_transport_failures(monkeypatch):
    import gaswise.providers.http.egress_pool as egress_pool
    class Worker:
        def __init__(self, session_seconds, client_factory):
            self.client = client_factory()
            self.error = None
        async def snapshot(self, query, url, fuel):
            if self.error:
                raise self.error
            return self.client.proxy
        async def close(self):
            await self.client.aclose()
    now = [1000.0]
    monkeypatch.setattr(egress_pool.time, 'monotonic', lambda: now[0])
    pool = PooledGasBuddySession(['http://node-a:8888', 'http://node-b:8888'], worker_factory=Worker)
    key = keys_for_lanes()[1]

    # Non-transport failure: raises immediately without failover or quarantine.
    pool.workers[1].error = ProviderError('gasbuddy_http_api_rejected')
    token = collection_egress_key.set(key)
    try:
        with pytest.raises(ProviderError, match='^gasbuddy_http_api_rejected$'):
            await pool.snapshot(None, '', 1)
        pool.workers[1].error = None
        egress_pool._selection.set(None)
        assert await pool.snapshot(None, '', 1) == 'http://node-b:8888'
    finally:
        collection_egress_key.reset(token)

    # Transport failure: in-flight fails over to node-a and quarantines node-b.
    pool.workers[1].error = ProviderError('gasbuddy_http_unavailable')
    token = collection_egress_key.set(key)
    try:
        assert await pool.snapshot(None, '', 1) == 'http://node-a:8888'
        pool.workers[1].error = None
        # During quarantine, next queries stay on node-a.
        egress_pool._selection.set(None)
        assert await pool.snapshot(None, '', 1) == 'http://node-a:8888'
    finally:
        collection_egress_key.reset(token)

    # After quarantine expires, resolves back to node-b.
    now[0] += egress_pool.LANE_QUARANTINE_SECONDS + 1
    egress_pool._selection.set(None)
    token = collection_egress_key.set(key)
    try:
        assert await pool.snapshot(None, '', 1) == 'http://node-b:8888'
    finally:
        collection_egress_key.reset(token)
    await pool.close()


async def test_http_transport_failure_quarantines_lane_for_later_queries_only():
    import asyncio
    class Client:
        def __init__(self, proxy):
            self.proxy, self.error, self.calls = proxy, None, 0
        async def get(self, url, **kwargs):
            self.calls += 1
            if self.error:
                raise self.error
            return SimpleNamespace(status_code=429, proxy=self.proxy)
        post = get
        async def aclose(self):
            pass
    pool = PooledHTTPClient(['http://node-a:8888', 'http://node-b:8888'], client_factory=Client)

    async def query(*methods):
        # Each query runs in its own task, as shared-cache loads and API requests do.
        results = []
        for method in methods:
            try:
                results.append((await getattr(pool, method)('https://example.com')).proxy)
            except httpx.ConnectError:
                results.append('ConnectError')
        return results

    token = collection_egress_key.set(keys_for_lanes()[1])
    try:
        # An HTTP status is delivered from the pinned exit and never quarantines it.
        assert await asyncio.create_task(query('get')) == ['http://node-b:8888']
        pool.clients[1].error = httpx.ConnectError('private upstream detail')
        # The in-query retry stays on its pinned exit; the next query moves.
        assert await asyncio.create_task(query('post', 'get')) == ['ConnectError', 'ConnectError']
        assert await asyncio.create_task(query('get')) == ['http://node-a:8888']
        assert pool.clients[1].calls == 3
    finally:
        collection_egress_key.reset(token)


async def test_active_egress_probe_quarantines_unhealthy_lane_and_clears_on_recovery():
    class MockWorker:
        def __init__(self, session_seconds, client_factory):
            self.healthy = True
            self.closed = False
        async def probe(self, timeout=4.0):
            return self.healthy
        async def snapshot(self, query, url, fuel):
            return "ok"
        async def close(self):
            self.closed = True

    pool = PooledGasBuddySession(['http://node-a:8888', 'http://node-b:8888'], worker_factory=MockWorker)
    # Both healthy
    results = await pool.probe_all()
    assert results[0] is not None
    assert results[1] is not None
    assert len(pool.quarantine) == 0

    # Node B becomes unhealthy
    pool.workers[1].healthy = False
    assert await pool.probe_lane(1) is None
    assert 1 in pool.quarantine

    # Queries for lane 1 fall back to lane 0
    token = collection_egress_key.set(keys_for_lanes()[1])
    try:
        from gaswise.providers.http import egress_pool
        egress_pool._selection.set(None)
        assert egress_pool.selected_lane(2, quarantine=pool.quarantine) == 0
    finally:
        collection_egress_key.reset(token)

    # Node B recovers
    pool.workers[1].healthy = True
    recovered = await pool.probe_lane(1)
    assert recovered is not None
    assert 1 not in pool.quarantine
    await pool.close()


async def test_all_lanes_quarantined_falls_back_to_earliest_expiration_without_deadlock(monkeypatch):
    import gaswise.providers.http.egress_pool as egress_pool
    now = [1000.0]
    monkeypatch.setattr(egress_pool.time, 'monotonic', lambda: now[0])
    quarantine = {0: 1200.0, 1: 1100.0}
    token = collection_egress_key.set(keys_for_lanes()[0])
    try:
        egress_pool._selection.set(None)
        # Both lanes quarantined, but VPN is up: falls back to lane 1 (earliest expiration: 1100 < 1200)
        assert egress_pool.selected_lane(2, quarantine=quarantine) == 1
    finally:
        collection_egress_key.reset(token)


async def test_pooled_http_client_clears_quarantine_on_successful_response():
    from gaswise.providers.http.egress_pool import PooledHTTPClient
    class FakeClient:
        def __init__(self, proxy):
            self.proxy = proxy
        async def post(self, url, **kwargs):
            return "ok"
        async def aclose(self):
            pass

    quarantine = {0: 9999.0}
    client = PooledHTTPClient(['http://a:8888'], client_factory=FakeClient, quarantine=quarantine)
    assert 0 in client.quarantine
    resp = await client.post('https://example.com')
    assert resp == 'ok'
    assert 0 not in client.quarantine


