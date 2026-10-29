"""Pinned per-query egress sessions with transport-layer failover. Source budgets remain global.

Lane availability comes from the operator-owned heartbeat produced by the VPN
supervisor. A query resolves one lane before provider HTTP. When no lane is usable
the source defers with ``pricing_egress_unavailable`` instead of making an unverified
direct request. A GasBuddy transport failure quarantines that lane locally for a few
minutes and immediately fails over to an alternate healthy lane in the same query.
An HTTP status response never quarantines a lane. The diagnostic in
``scripts/diagnostics/egress_lanes.py`` proves a lane with an HTTPS 200 and a US
location rather than container health alone.
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
# A transport failure on a heartbeat-healthy exit keeps later queries off it briefly.
LANE_QUARANTINE_SECONDS = 300


def lane_index(size):
    digest = hashlib.sha256(collection_egress_key.get().encode()).digest()
    return int.from_bytes(digest[:8], "big") % size


def _record_lane(index):
    trace = collection_attempt.get()
    if trace is not None:
        trace['egress_lane'] = index
    return index


def quarantine_lane(quarantine, index):
    """Keep later queries off an exit whose transport just failed."""
    quarantine[index] = time.monotonic() + LANE_QUARANTINE_SECONDS


def selected_lane(size, health_file=None, quarantine=None):
    """Resolve once per query; offline or quarantined lanes fall back before provider HTTP."""
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
    now = time.monotonic()
    unavailable |= {lane for lane, until in (quarantine or {}).items() if until > now}
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
        self.quarantine = {}
        factory = client_factory or (lambda proxy: httpx.AsyncClient(
            proxy=proxy, trust_env=False, http2=True, timeout=20, follow_redirects=False))
        self.clients = [factory(str(proxy)) for proxy in proxies]

    async def get(self, url, **kwargs):
        return await self._request("get", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._request("post", url, **kwargs)

    async def _request(self, method, url, **kwargs):
        index = selected_lane(len(self.clients), self.health_file, self.quarantine)
        try:
            return await getattr(self.clients[index], method)(url, **kwargs)
        except httpx.TransportError:
            quarantine_lane(self.quarantine, index)
            raise

    async def aclose(self):
        for client in self.clients:
            await client.aclose()


class PooledGasBuddySession:
    """Keep CSRF, cookies and browser protocol together on each fixed US exit."""
    def __init__(self, proxies, *, session_seconds=600, worker_factory=None, health_file=None):
        self.health_file = health_file
        self.request_budget = None
        self.quarantine = {}
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
        max_attempts = max(1, len(self.workers))
        for attempt in range(max_attempts):
            index = selected_lane(len(self.workers), self.health_file, self.quarantine)
            worker = self.workers[index]
            worker.request_budget = self.request_budget
            try:
                return await worker.snapshot(query, url, fuel)
            except ProviderError as error:
                # The whole snapshot failed on this lane; quarantine the exit.
                # If other healthy exits remain, fail over immediately in the same snapshot.
                if str(error) == 'gasbuddy_http_unavailable':
                    quarantine_lane(self.quarantine, index)
                    _selection.set(None)
                    now = time.monotonic()
                    quarantined = {lane for lane, until in self.quarantine.items() if until > now}
                    if attempt + 1 < max_attempts and any(i not in quarantined for i in range(len(self.workers))):
                        continue
                raise

    async def close(self):
        for worker in self.workers:
            await worker.close()
