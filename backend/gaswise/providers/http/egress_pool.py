"""Pinned per-query egress sessions. Source budgets remain global, with no HTTP failover.

Lane availability comes from the operator-owned heartbeat produced by the VPN
supervisor. A query resolves one lane before provider HTTP and keeps it for every
page, so a lane is never switched mid-query. When no lane is usable the source
defers with ``pricing_egress_unavailable`` instead of making an unverified direct
request; the diagnostic in ``scripts/diagnostics/egress_lanes.py`` proves a lane
with an HTTPS 200 and a US location rather than container health alone.
"""
import hashlib
import json
import time
from contextvars import ContextVar
from pathlib import Path

import httpx

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.shared_cache import collection_attempt, collection_egress_key
from gaswise.providers.gasbuddy.http_session import GasBuddyHTTPSession
from gaswise.providers.http.curl_client import CurlHTTPClient

_selection = ContextVar("pricing_egress_selection", default=None)


def lane_index(size):
    digest = hashlib.sha256(collection_egress_key.get().encode()).digest()
    return int.from_bytes(digest[:8], "big") % size


def _record_lane(index):
    trace = collection_attempt.get()
    if trace is not None:
        trace['egress_lane'] = index
    return index


def selected_lane(size, health_file=None):
    """Resolve once per query; offline VPN lanes fall back before provider HTTP."""
    key = (collection_egress_key.get(), size, str(health_file))
    previous = _selection.get()
    if previous is not None and previous[0] == key:
        return _record_lane(previous[1])
    unavailable = set()
    if health_file is not None:
        try:
            path = Path(health_file)
            if time.time() - path.stat().st_mtime > 30:
                raise ValueError('stale_lane_health')
            data = json.loads(path.read_text())
            rows = data['unavailable_lanes']
            if not isinstance(rows, list) or not all(type(row) is int for row in rows):
                raise ValueError('invalid_lane_health')
            unavailable = set(rows)
        except (OSError, ValueError, KeyError, TypeError):
            unavailable = set(range(1, size))
    available = [index for index in range(size) if index not in unavailable]
    if not available:
        # A source failure, not a programming error: callers report the source as
        # deferred and the ranking keeps other evidence instead of returning 500.
        raise ProviderError('pricing_egress_unavailable')
    index = lane_index(size)
    if index not in available:
        index = available[0]
    _selection.set((key, index))
    return _record_lane(index)


class PooledHTTPClient:
    """Separate cookie jars per exit; provider-supplied authentication headers win."""
    def __init__(self, proxies, *, client_factory=None, health_file=None):
        self.health_file = health_file
        factory = client_factory or (lambda proxy: httpx.AsyncClient(
            proxy=proxy, trust_env=False, http2=True, timeout=20, follow_redirects=False))
        self.clients = [factory(str(proxy)) for proxy in proxies]

    async def get(self, url, **kwargs):
        return await self.clients[selected_lane(len(self.clients), self.health_file)].get(url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.clients[selected_lane(len(self.clients), self.health_file)].post(url, **kwargs)

    async def aclose(self):
        for client in self.clients:
            await client.aclose()


class PooledGasBuddySession:
    """Keep CSRF, cookies and browser protocol together on each fixed US exit."""
    def __init__(self, proxies, *, session_seconds=600, worker_factory=None, health_file=None):
        self.health_file = health_file
        self.request_budget = None
        self.workers = []
        for index, proxy in enumerate(proxies):
            # Consistent libcurl browser defaults include matching protocol headers.
            profile = ("chrome", "safari")[index % 2]
            def factory(proxy=str(proxy), profile=profile):
                return CurlHTTPClient(allowed_hosts={"www.gasbuddy.com"}, preserve_cookies=True,
                                      proxy=proxy, profile=profile)
            worker = (worker_factory or GasBuddyHTTPSession)(
                session_seconds=session_seconds, client_factory=factory)
            self.workers.append(worker)

    async def snapshot(self, query, url, fuel):
        worker = self.workers[selected_lane(len(self.workers), self.health_file)]
        worker.request_budget = self.request_budget
        return await worker.snapshot(query, url, fuel)

    async def close(self):
        for worker in self.workers:
            await worker.close()
