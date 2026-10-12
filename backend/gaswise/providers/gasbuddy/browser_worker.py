"""Render the normal anonymous website and observe its own SearchPrices response.

Uses a fresh browser context, no user profile, cookie import, spoofing, stealth,
manual challenge solving or handcrafted GraphQL requests. A rejection remains a
source error. Browser process is reused; contexts and page responses are not cached.
"""

import asyncio
import json

from playwright.async_api import Error as BrowserError
from playwright.async_api import TimeoutError as BrowserTimeout
from playwright.async_api import async_playwright

from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError


class GasBuddyBrowserWorker:
    def __init__(self, channel="chrome", timeout_seconds=35, headless=True):
        self.channel = channel
        self.headless = headless
        self.timeout_ms = timeout_seconds * 1000
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        if self._browser is None or not self._browser.is_connected():
            # Default browser settings. No user data directory or custom UA/fingerprint.
            self._browser = await self._playwright.chromium.launch(
                channel=self.channel, headless=self.headless
            )

    async def snapshot(self, query: Search, url: str, fuel: int):
        async with self._lock:
            context = None
            try:
                await self._ensure_browser()
                context = await self._browser.new_context()
                page = await context.new_page()
                page.set_default_timeout(self.timeout_ms)

                def price_response(response):
                    if (
                        response.url != "https://www.gasbuddy.com/graphql"
                        or response.request.method != "POST"
                    ):
                        return False
                    try:
                        body = response.request.post_data_json
                        variables = body.get("variables", {})
                        return (
                            body.get("operationName") == "SearchPrices"
                            and variables.get("search")
                            == (getattr(query, "search", None) or query.postal_code)
                            and variables.get("fuel") == fuel
                        )
                    except (ValueError, TypeError, AttributeError):
                        return False

                async with page.expect_response(price_response, timeout=self.timeout_ms) as price_event:
                    navigation = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    if navigation is None or navigation.status >= 400:
                        raise ProviderError("gasbuddy_browser_navigation_rejected")
                response = await price_event.value
                if not response.ok:
                    raise ProviderError("gasbuddy_browser_price_request_rejected")
                data = await response.json()
                if data.get("errors"):
                    raise ProviderError("gasbuddy_browser_query_rejected")
                listing = data["data"]["locationBySearchTerm"]["stations"]
                html = await page.content()
                marker = "window.__APOLLO_STATE__ = "
                state, _ = json.JSONDecoder().raw_decode(html[html.index(marker) + len(marker) :])
                return state, listing
            except BrowserTimeout:
                raise ProviderError("gasbuddy_browser_timeout_or_challenge") from None
            except BrowserError:
                raise ProviderError("gasbuddy_browser_unavailable") from None
            except (ValueError, KeyError, TypeError, AttributeError):
                raise ProviderError("gasbuddy_browser_schema_changed") from None
            finally:
                if context is not None:
                    try:
                        await asyncio.wait_for(asyncio.shield(context.close()), timeout=5)
                    except (BrowserError, TimeoutError):
                        # A broken context is not reused on a later request.
                        await self.close()

    async def close(self):
        try:
            if self._browser is not None:
                await self._browser.close()
        finally:
            self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None
