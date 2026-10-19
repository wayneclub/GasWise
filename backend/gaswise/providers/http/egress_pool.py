"""Pinned per-query egress sessions. Source budgets remain global, with no HTTP failover."""
import hashlib

import httpx

from gaswise.domain.pricing.shared_cache import collection_egress_key
from gaswise.providers.gasbuddy.http_session import GasBuddyHTTPSession
from gaswise.providers.http.curl_client import CurlHTTPClient


def lane_index(size):
    digest = hashlib.sha256(collection_egress_key.get().encode()).digest()
    return int.from_bytes(digest[:8], "big") % size


class PooledHTTPClient:
    """Separate cookie jars per exit; provider-supplied authentication headers win."""
    def __init__(self, proxies, *, client_factory=None):
        factory = client_factory or (lambda proxy: httpx.AsyncClient(
            proxy=proxy, trust_env=False, http2=True, timeout=20, follow_redirects=False))
        self.clients = [factory(str(proxy)) for proxy in proxies]

    async def get(self, url, **kwargs):
        return await self.clients[lane_index(len(self.clients))].get(url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.clients[lane_index(len(self.clients))].post(url, **kwargs)

    async def aclose(self):
        for client in self.clients:
            await client.aclose()


class PooledGasBuddySession:
    """Keep CSRF, cookies and browser protocol together on each fixed US exit."""
    def __init__(self, proxies, *, session_seconds=600, worker_factory=None):
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
        worker = self.workers[lane_index(len(self.workers))]
        worker.request_budget = self.request_budget
        return await worker.snapshot(query, url, fuel)

    async def close(self):
        for worker in self.workers:
            await worker.close()
