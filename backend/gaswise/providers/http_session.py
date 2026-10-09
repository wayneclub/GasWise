"""Browser-free anonymous price client: homepage token/cookies -> normal API.

No Chrome, JavaScript engine, imported clearance cookie or user profile. Credentials
stay only in this HTTP client's memory until expiry/shutdown. Each query obtains new
prices and metadata from the API; no historical/current price response is cached.
"""

import asyncio
import re
import time

import httpx

from gaswise.models import Search, gasbuddy_variables
from gaswise.providers.base import ProviderError
from gaswise.providers.gasbuddy_web import PRICE_QUERY

LANDING = "https://www.gasbuddy.com/"
GRAPHQL = "https://www.gasbuddy.com/graphql"
# These station fields were verified via the same anonymous API on 2026-10-09.
METADATA_QUERY = PRICE_QUERY.replace(
    "      results {\n        id",
    "      results {\n        id\n        name\n        priceUnit\n        address { country line1 locality postalCode region }",
)


class GasBuddyHTTPSession:
    def __init__(self, session_seconds=600, client_factory=None):
        self.session_seconds = session_seconds
        self._factory = client_factory or (
            lambda: httpx.AsyncClient(
                http2=True,
                follow_redirects=True,
                timeout=httpx.Timeout(15),
                headers={"User-Agent": "GasWise/0.5 anonymous fuel comparison"},
            )
        )
        self._client = None
        self._csrf = None
        self._created_at = 0
        self._expiry_task = None
        self._lock = asyncio.Lock()

    async def _bootstrap(self):
        self._client = self._factory()
        response = await self._client.get(LANDING)
        if response.headers.get("cf-mitigated") == "challenge":
            raise ProviderError("gasbuddy_http_bootstrap_challenge")
        if not response.is_success:
            raise ProviderError("gasbuddy_http_bootstrap_rejected")
        match = re.search(r'window\.gbcsrf\s*=\s*"([^"\n]+)"', response.text)
        if match is None:
            raise ProviderError("gasbuddy_http_csrf_missing")
        self._csrf = match.group(1)
        self._created_at = time.monotonic()
        self._expiry_task = asyncio.create_task(self._expire_idle_session(self._client))

    async def snapshot(self, query: Search, _url: str, fuel: int):
        async with self._lock:
            try:
                if self._client is None or time.monotonic() - self._created_at >= self.session_seconds:
                    await self._discard_session()
                    await self._bootstrap()
                response = await self._client.post(
                    GRAPHQL,
                    headers={
                        "Origin": "https://www.gasbuddy.com",
                        "Referer": LANDING,
                        "Accept": "*/*",
                        "apollo-require-preflight": "true",
                        "gbcsrf": self._csrf,
                    },
                    json={
                        "operationName": "SearchPrices",
                        "variables": gasbuddy_variables(query, fuel),
                        "query": METADATA_QUERY,
                    },
                )
                if response.headers.get("cf-mitigated") == "challenge":
                    raise ProviderError("gasbuddy_http_api_challenge")
                if not response.is_success:
                    raise ProviderError("gasbuddy_http_api_rejected")
                data = response.json()
                if data.get("errors"):
                    raise ProviderError("gasbuddy_http_query_rejected")
                listing = data["data"]["locationBySearchTerm"]["stations"]
                # Produce the provider's existing metadata envelope using THIS API response.
                # Homepage has no search-specific stations, so its Apollo cache is not used.
                state = {f"Station:{station['id']}": station for station in listing["results"]}
                return state, listing
            except httpx.RequestError:
                await self._discard_session()
                raise ProviderError("gasbuddy_http_unavailable") from None
            except (ValueError, KeyError, TypeError, AttributeError):
                await self._discard_session()
                raise ProviderError("gasbuddy_http_schema_changed") from None
            except BaseException:
                await self._discard_session()
                raise

    async def _expire_idle_session(self, client):
        try:
            await asyncio.sleep(self.session_seconds)
            async with self._lock:
                if self._client is client:
                    await self._discard_session()
        except asyncio.CancelledError:
            pass

    async def _discard_session(self):
        task, self._expiry_task = self._expiry_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        client, self._client = self._client, None
        self._csrf = None
        self._created_at = 0
        if client is not None:
            await client.aclose()

    async def close(self):
        await self._discard_session()
