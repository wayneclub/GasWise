"""Run from backend with uv. Reads local token without echoing secrets."""

import argparse
import json
import time

import httpx

from gaswise.contracts.sources import GasBuddyPrices
from gaswise.app.settings import Settings

parser = argparse.ArgumentParser()
parser.add_argument("--repeat", type=int, default=1, choices=range(1, 4))
args = parser.parse_args()
settings = Settings()
headers = {"Authorization": "Bearer " + settings.api_token.get_secret_value()}
query = {
    "origin": {"lat": 34.03938, "lng": -118.2663},
    "postal_code": "90015",
    "fuel_type": "premium",
    "payment_type": "credit",
    "max_results": 10,
}
fetch_times = []
with httpx.Client(timeout=60, base_url="http://127.0.0.1:8000") as client:
    for index in range(args.repeat):
        started = time.monotonic()
        response = client.post("/v1/sources/gasbuddy/prices", json=query, headers=headers)
        if not response.is_success:
            print(
                json.dumps(
                    {"status": response.status_code, "error": response.json().get("detail")},
                    ensure_ascii=False,
                )
            )
            raise SystemExit(1)
        data = GasBuddyPrices.model_validate(response.json())
        assert data.transport in {"http", "browser", "session_http"} and data.prices, (
            "Expected live provider data"
        )
        assert all(p.source == "gasbuddy_web" and p.payment_type == "credit" for p in data.prices)
        fetch_times.append(data.fetched_at)
        print(
            json.dumps(
                {
                    "request": index + 1,
                    "http_status": response.status_code,
                    "transport": data.transport,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "fetched_at": data.fetched_at.isoformat(),
                    "quote_count": len(data.prices),
                    "prices": [
                        {
                            "station": p.name,
                            "address": p.address,
                            "price": str(p.price_per_gallon),
                            "payment": p.payment_type,
                            "price_updated_at": p.price_updated_at.isoformat()
                            if p.price_updated_at
                            else None,
                        }
                        for p in data.prices
                    ],
                },
                ensure_ascii=False,
            )
        )
assert fetch_times == sorted(set(fetch_times)), "Each request must have a new fetch timestamp"
