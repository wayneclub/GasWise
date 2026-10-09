# GasWise — Fill Smart. Spend Less.

Independent FastAPI backend for live price collection, source comparison and true refueling costs. No frontend dependencies. Decimal money is serialized as USD strings; volume is US gallons.

## Run

```sh
cd backend
uv sync --locked
cp -n .env.example .env
uv run uvicorn gaswise.main:app --host 127.0.0.1 --port 8000
```

[Interactive API](http://127.0.0.1:8000/docs). This workspace's private `.env` selects **prices_only**, with real GasBuddy prices via **pure HTTP**. No Chrome, Playwright import or browser-bootstrap step is required. A fresh installation without that `.env` defaults to synthetic demo. `cp -n` preserves existing configuration.

## Live GasBuddy prices

The provider obtains anonymous cookies and `window.gbcsrf` from the public homepage and calls SearchPrices directly over HTTP/2. Station names/addresses are returned by the API, so the challenged search HTML is unnecessary. Each query fetches new prices. Cookie/token state expires after 600 seconds by default and is kept only in memory. No imported user cookies or automatic browser fallback.

```sh
cd backend
uv run python ../scripts/check_live_gasbuddy.py --repeat 3
uv run python ../scripts/check_no_browser_runtime.py
```

The helper reads the local service token without printing it. The cold-start check forbids Playwright imports and creates an empty HTTP cookie jar. Real checks returned four Premium credit quotes, with cold HTTP about 1.07 seconds and reused-session HTTP about 0.24 seconds. These are local measurements.

Use `POST /v1/sources/gasbuddy/prices` with the [example request](contracts/gasbuddy-search-example.json) and `Authorization: Bearer <GasWise token>`. Current raw prices are live; route recommendations remain disabled (`503 routing_provider_not_configured`) until routing credentials are supplied. Premium does not verify numeric 91 octane. Report time is separate from retrieval time. Cash and credit are kept distinct.

The protocol is an observed website API, not a contracted public API. Source rejection is an explicit error. See [integration and evidence](docs/gasbuddy-integration.md).

## Cost recommendations

Set `GASWISE_MODE=google`, `GASWISE_GOOGLE_API_KEY` and `GASWISE_API_TOKEN`; enable Places API (New) and Routes API in a billed project. API keys stay server-side. Each query can use Nearby Search, Text Search to resolve GasBuddy addresses, one baseline route and up to 30 candidate routes. Retries may increase provider calls. Google coverage, routes and billing have not been live-verified without a key.

`POST /v1/recommendations` returns purchase/detour/time costs, source evidence and a decision. `best_value` uses conservative observed price bounds; `cheapest_overall` uses selected nominal quotes. Source preference reflects user choice, not verified vendor accuracy. Costs assume fixed gallons and station price for extra fuel; no fill-to-full model, queue/toll/wear cost, or ML prediction is enabled.

`POST /v1/recommendations/stream` accepts the same body and emits SSE snapshots every 300 seconds by default, with keepalives every 15 seconds. Sessions last up to one hour. Closing the stream stops collection. Provider polling does not imply a station changed its price. Browser clients use fetch streaming for POST/auth headers.

## Deployment and testing

The production default excludes browser packages/runtime:

```sh
cd backend
uv sync --locked --no-dev
uv run --no-dev uvicorn gaswise.main:app --host 127.0.0.1 --port 8000
```

For development:

```sh
uv sync --locked
uv run pytest -q
uv run ruff check gaswise tests ../scripts
uv run python ../scripts/export_openapi.py
```

Older browser transports are optional (`uv sync --extra browser`) and never selected automatically. For public deployment, use per-user/session authentication, a gateway, rate limits and provider quotas. The static local service token should not be embedded in a public browser bundle. Google content is not archived; HTTP responses use no-store.

[Backend design](docs/backend-design.md) · [OpenAPI contract](contracts/openapi.json) · [Route example](contracts/search-example.json)

Brand dropdown: `GET /v1/sources/gasbuddy/brands` returns 26 verified brand name/ID options and an All Station Brands option. See [integration documentation](docs/gasbuddy-integration.md#brand-dropdown).

Independent price services can now be added through `GASWISE_PRICE_SOURCES`, using the versioned normalized feed contract. Source discovery: `GET /v1/sources`; normalized quote aggregation: `POST /v1/prices`. See [integration guide](docs/price-source-integration.md).

## AAA regional averages

`GET /v1/sources/aaa/averages?state=CA` (same Bearer authentication) fetches the latest public AAA daily averages without an API key or browser. Accepts US state abbreviations and DC, defaults to CA. Available in every service mode; discovery is under `regional_average_sources` in `/v1/sources`.

Returns `price_as_of`, `retrieved_at`, source link, USD per US gallon, and `regions` at state, metro and county levels. State/metro `prices` include `current`, `yesterday`, `week_ago`, `month_ago`, `year_ago`, each with `regular`, `mid_grade`, `premium`, `diesel`. Decimal prices remain exact strings. County data provides current regular only; missing county prices are null. `county_status=unavailable` means the county map could not be read; state/metro data can still succeed.

AAA publishes daily averages, not real-time pump prices. Every request retrieves the public page, with no stored fallback; source errors return 502. County maps are a separate upstream request and may not update atomically with tables. Averages are regional context and are never substituted for individual station quotes or cost rankings. Public HTML/map formats may change.

Live verification on 2026-10-09: CA returned 1 state, 31 metros, 58 counties; NY returned 1 state and 16 metros, with county data unavailable. No frontend is included in this backend workspace. See the generated OpenAPI for the typed response contract.

## Google fuel prices without routes

`POST /v1/sources/google/prices` searches up to 20 nearby places for the selected
fuel price using one successful Nearby Search request. Available alongside GasBuddy
in `prices_only` mode after adding `GASWISE_GOOGLE_API_KEY` and keeping the service
token configured. No Routes API is needed for this endpoint. See
[setup, request example, billing and attribution](docs/google-integration.md).
