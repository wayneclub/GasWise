"""Real cold-start API check with Playwright imports explicitly forbidden.

Run from backend: uv run python ../scripts/smoke/check_no_browser_runtime.py
Creates its own FastAPI lifespan and an empty HTTP cookie jar; imports no browser
library and uses no saved session. Token/cookie values are never printed.
"""

import importlib.abc
import json
import sys
import time


class ForbidBrowserImport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "playwright" or fullname.startswith("playwright."):
            raise ImportError("Browser library imports are forbidden for this cold-start check")
        return None


sys.meta_path.insert(0, ForbidBrowserImport())
from fastapi.testclient import TestClient  # noqa: E402

from gaswise.main import create_app  # noqa: E402
from gaswise.contracts.sources import GasBuddyPrices
from gaswise.app.settings import Settings  # noqa: E402

settings = Settings()
assert settings.gasbuddy_web_transport == "http"
headers = {"Authorization": "Bearer " + settings.api_token.get_secret_value()}
query = {
    "origin": {"lat": 34.03938, "lng": -118.2663},
    "postal_code": "90015",
    "fuel_type": "premium",
    "payment_type": "credit",
    "max_results": 10,
}
with TestClient(create_app(settings)) as api:
    for number in range(2):
        start = time.monotonic()
        response = api.post("/v1/sources/gasbuddy/prices", json=query, headers=headers)
        if response.status_code != 200:
            print(json.dumps({"status": response.status_code, "detail": response.json().get("detail")}))
            raise SystemExit(1)
        data = GasBuddyPrices.model_validate(response.json())
        assert data.transport == "http" and data.prices
        assert all(p.source == "gasbuddy_web" and p.payment_type == "credit" for p in data.prices)
        print(
            json.dumps(
                {
                    "request": number + 1,
                    "status": response.status_code,
                    "transport": data.transport,
                    "quote_count": len(data.prices),
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                    "playwright_loaded": any(
                        m == "playwright" or m.startswith("playwright.") for m in sys.modules
                    ),
                }
            )
        )
