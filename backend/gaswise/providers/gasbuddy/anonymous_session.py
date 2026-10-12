"""Bootstrap one fresh anonymous session, then use its shared HTTP cookie jar.

Session credentials stay in memory for a bounded lifetime. No user-profile cookies
or token values are exported. HTTP rejection invalidates the session and is surfaced,
not retried or converted into a browser-price fallback.
"""

import asyncio
import json
import re
import time

from playwright.async_api import Error as BrowserError
from playwright.async_api import TimeoutError as BrowserTimeout

from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.providers.gasbuddy.browser_worker import GasBuddyBrowserWorker


class GasBuddyAnonymousSession(GasBuddyBrowserWorker):
    def __init__(self, channel="chrome", timeout_seconds=35, headless=False, session_seconds=600):
        super().__init__(channel, timeout_seconds, headless)
        self.session_seconds = session_seconds
        self._context = None
        self._state = None
        self._query_body = None
        self._csrf = None
        self._session_key = None
        self._created_at = 0
        self._expiry_task = None

    async def _bootstrap(self, query: Search, url: str, fuel: int):
        await self._ensure_browser()
        context = await self._browser.new_context()
        try:
            page = await context.new_page()
            page.set_default_timeout(self.timeout_ms)

            def matches(response):
                if response.url != "https://www.gasbuddy.com/graphql" or response.request.method != "POST":
                    return False
                try:
                    body = response.request.post_data_json
                    variables = body.get("variables", {})
                    return (
                        body.get("operationName") == "SearchPrices"
                        and variables.get("search") == (getattr(query, "search", None) or query.postal_code)
                        and variables.get("fuel") == fuel
                    )
                except (ValueError, TypeError, AttributeError):
                    return False

            async with page.expect_response(matches, timeout=self.timeout_ms) as event:
                navigation = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                if navigation is None or navigation.status >= 400:
                    raise ProviderError("gasbuddy_session_bootstrap_rejected")
            response = await event.value
            if not response.ok:
                raise ProviderError("gasbuddy_session_bootstrap_price_rejected")
            html = await page.content()
            marker = "window.__APOLLO_STATE__ = "
            state, _ = json.JSONDecoder().raw_decode(html[html.index(marker) + len(marker) :])
            match = re.search(r'window\.gbcsrf\s*=\s*"([^"\n]+)"', html)
            if match is None or match.group(1) != response.request.headers.get("gbcsrf"):
                raise ProviderError("gasbuddy_session_csrf_unverified")
            body = response.request.post_data_json
            # Keep the session/cookies, but close the rendered page. Subsequent queries use HTTP.
            await page.close()
            return context, state, body, match.group(1)
        except BaseException:
            await context.close()
            raise

    async def snapshot(self, query: Search, url: str, fuel: int):
        async with self._lock:
            try:
                key = (
                    getattr(query, "search", None) or query.postal_code,
                    fuel,
                    query.payment_type,
                    getattr(query, "brand_id", None),
                )
                if (
                    self._context is None
                    or self._session_key != key
                    or time.monotonic() - self._created_at >= self.session_seconds
                ):
                    await self._discard_session()
                    self._context, self._state, self._query_body, self._csrf = await self._bootstrap(
                        query, url, fuel
                    )
                    self._session_key, self._created_at = key, time.monotonic()
                    self._expiry_task = asyncio.create_task(self._expire_idle_session(self._context))
                response = await self._context.request.post(
                    "https://www.gasbuddy.com/graphql",
                    data=self._query_body,
                    headers={
                        "Origin": "https://www.gasbuddy.com",
                        "Referer": url,
                        "Accept": "*/*",
                        "apollo-require-preflight": "true",
                        "gbcsrf": self._csrf,
                    },
                    timeout=15000,
                )
                if not response.ok:
                    raise ProviderError("gasbuddy_session_http_rejected")
                data = await response.json()
                if data.get("errors"):
                    raise ProviderError("gasbuddy_session_query_rejected")
                return self._state, data["data"]["locationBySearchTerm"]["stations"]
            except BrowserTimeout:
                await self._discard_session()
                raise ProviderError("gasbuddy_session_timeout_or_challenge") from None
            except BrowserError:
                await self._discard_session()
                raise ProviderError("gasbuddy_session_unavailable") from None
            except (ValueError, TypeError, KeyError, AttributeError):
                await self._discard_session()
                raise ProviderError("gasbuddy_session_schema_changed") from None
            except BaseException:
                await self._discard_session()
                raise

    async def _expire_idle_session(self, context):
        try:
            await asyncio.sleep(self.session_seconds)
            async with self._lock:
                if self._context is context:
                    await self._discard_session()
        except asyncio.CancelledError:
            pass

    async def _discard_session(self):
        task, self._expiry_task = self._expiry_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        context, self._context = self._context, None
        self._state = self._query_body = self._csrf = self._session_key = None
        self._created_at = 0
        if context is not None:
            try:
                await context.close()
            except BrowserError:
                pass

    async def close(self):
        await self._discard_session()
        await super().close()
