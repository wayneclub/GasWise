"""Compare normal loading and HTTP using one new anonymous cookie jar.

Prints statuses/names/booleans only, never cookie/token values. No existing profile
is opened. Rejected requests are reported without retries.
Run from backend: uv run python ../scripts/diagnostics/gasbuddy/probe_gasbuddy_session.py
"""

import asyncio
import json
import re

from playwright.async_api import async_playwright

URL = "https://www.gasbuddy.com/home?search=90015&fuel=3&method=credit&maxAge=0"


async def probe():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=False)
        try:
            context = await browser.new_context()
            try:
                page = await context.new_page()
                async with page.expect_response(
                    lambda response: (
                        response.url == "https://www.gasbuddy.com/graphql"
                        and response.request.method == "POST"
                    ),
                    timeout=35000,
                ) as event:
                    navigation = await page.goto(URL, wait_until="domcontentloaded", timeout=35000)
                    if navigation.status >= 400:
                        print(json.dumps({"navigation_status": navigation.status}))
                        return
                response = await event.value
                request = response.request
                headers = request.headers
                body = request.post_data_json
                html = await page.content()
                match = re.search(r'window\.gbcsrf\s*=\s*"([^"\n]+)"', html)
                cookie_names = sorted({c["name"] for c in await context.cookies([URL])})
                print(
                    json.dumps(
                        {
                            "browser_graphql_status": response.status,
                            "has_authorization": "authorization" in headers,
                            "csrf_in_html": match is not None,
                            "csrf_header_matches_html": match is not None
                            and headers.get("gbcsrf") == match.group(1),
                            "cookie_names": cookie_names,
                        }
                    )
                )
                if not response.ok or match is None:
                    return
                # This HTTP API shares the context's anonymous cookie jar.
                api = await context.request.post(
                    "https://www.gasbuddy.com/graphql",
                    data=body,
                    headers={
                        "Origin": "https://www.gasbuddy.com",
                        "Referer": URL,
                        "Accept": "*/*",
                        "apollo-require-preflight": "true",
                        "gbcsrf": match.group(1),
                    },
                    timeout=15000,
                )
                diagnostic = {
                    "shared_cookie_http_status": api.status,
                    "content_type": api.headers.get("content-type"),
                }
                if api.ok:
                    payload = await api.json()
                    stations = (
                        payload.get("data", {})
                        .get("locationBySearchTerm", {})
                        .get("stations", {})
                        .get("results", [])
                    )
                    diagnostic["station_count"] = len(stations)
                    diagnostic["graphql_has_errors"] = bool(payload.get("errors"))
                else:
                    # Generic categories only; error bodies can reflect request credentials.
                    text = (await api.text()).lower()
                    diagnostic["mentions_csrf"] = "csrf" in text
                    diagnostic["mentions_cloudflare"] = "cloudflare" in text
                    diagnostic["mentions_challenge"] = "challenge" in text
                print(json.dumps(diagnostic))
            finally:
                await context.close()
        finally:
            await browser.close()


asyncio.run(probe())
