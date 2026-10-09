"""Probe Waze with a fresh standard Chrome session; not a production price provider."""

import argparse
import asyncio
import json

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright


async def check(headful):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=not headful)
        try:
            context = await browser.new_context(locale="en-US")
            page = await context.new_page()
            observations = []

            def observe(response):
                if "SearchServer/mozi" in response.url or response.url.endswith("/searchLocations"):
                    observations.append({"service": "fuel_or_search", "status": response.status})

            page.on("response", observe)
            navigation = await page.goto(
                "https://www.waze.com/en-US/editor", wait_until="domcontentloaded", timeout=30000
            )
            print(json.dumps({"step": "editor", "status": navigation.status if navigation else None}), flush=True)
            if navigation is None or not navigation.ok:
                return 1
            try:
                practice = page.get_by_role("link", name="Try practice mode", exact=False)
                await practice.click(timeout=20000)
                search = page.get_by_role("textbox", name="Search location", exact=False)
                await search.fill("76 4600 Melrose Ave Los Angeles", timeout=10000)
                await page.get_by_text("Los Angeles", exact=False).first.wait_for(timeout=10000)
                print(json.dumps({"step": "practice_search", "observations": observations}), flush=True)
            except PlaywrightTimeout:
                print(json.dumps({"step": "practice_search", "status": "ui_timeout"}), flush=True)
            response = await context.request.get(
                "https://www.waze.com/SearchServer/mozi",
                params={
                    "lon": -118.3008564,
                    "lat": 34.0833736,
                    "format": "PROTO_JSON_FULL",
                    "venue_id": "venues.158400853.1584008528.5847665",
                    "origin": "editor",
                },
                timeout=15000,
            )
            if not response.ok:
                print(json.dumps({"step": "fuel", "status": response.status, "prices_verified": False}), flush=True)
                return 1
            try:
                data = await response.json()
            except ValueError:
                print(json.dumps({"step": "fuel", "status": "invalid_json", "prices_verified": False}), flush=True)
                return 1
            fuels = [
                {key: product.get(key) for key in ("id", "price", "last_updated")}
                for product in (data.get("venue") or {}).get("product", [])
                if str(product.get("id", "")).startswith("gas.")
            ]
            print(json.dumps({"step": "fuel", "fuels": fuels, "prices_verified": bool(fuels)}), flush=True)
            return 0 if fuels else 1
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headful", action="store_true")
    raise SystemExit(asyncio.run(check(parser.parse_args().headful)))
