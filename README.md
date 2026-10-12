# GasWise — Fill Smart. Spend Less.

The React frontend lives in [frontend/](frontend/README.md); it talks to this backend through a token-injecting proxy.

Independent FastAPI backend for live price collection, source comparison and true refueling costs. No frontend dependencies. Decimal money is serialized as USD strings; volume is US gallons.

## Run

```sh
cd backend
uv sync --locked
cp -n .env.example .env
uv run uvicorn gaswise.main:app --host 127.0.0.1 --port 8000
```

[Interactive API](http://127.0.0.1:8000/docs). This workspace's private `.env` selects **prices_only**, with real GasBuddy prices via **pure HTTP**. No Chrome, Playwright import or browser-bootstrap step is required. A fresh installation without that `.env` defaults to synthetic demo. `cp -n` preserves existing configuration.

Waze HTTP prices are now integrated as an opt-in source in this workspace.
See [Waze setup and session lifecycle](docs/waze-integration.md) for the raw,
normalized and smart-search endpoints. Saved credentials may expire; web
Google login is not a verified replacement for native-protocol credentials.

## Live GasBuddy prices

The provider obtains anonymous cookies and `window.gbcsrf` from the public homepage and calls SearchPrices directly over HTTP/2. Station names/addresses are returned by the API, so the challenged search HTML is unnecessary. Each query fetches new prices. Cookie/token state expires after 600 seconds by default and is kept only in memory. No imported user cookies or automatic browser fallback.

```sh
cd backend
uv run python ../scripts/smoke/check_live_gasbuddy.py --repeat 3
uv run python ../scripts/smoke/check_no_browser_runtime.py
```

The helper reads the local service token without printing it. The cold-start check forbids Playwright imports and creates an empty HTTP cookie jar. Real checks returned four Premium credit quotes, with cold HTTP about 1.07 seconds and reused-session HTTP about 0.24 seconds. These are local measurements.

Use `POST /v1/sources/gasbuddy/prices` with the [example request](contracts/gasbuddy-search-example.json) and `Authorization: Bearer <GasWise token>`. Current raw prices are live; route recommendations remain disabled (`503 routing_provider_not_configured`) until routing credentials are supplied. Premium does not verify numeric 91 octane. Report time is separate from retrieval time. Cash and credit are kept distinct.

The protocol is an observed website API, not a contracted public API. Source rejection is an explicit error. See [integration and evidence](docs/gasbuddy-integration.md).

## Cost recommendations

For real routing, set `GASWISE_MODE=google`, `GASWISE_GOOGLE_API_KEY`, `GASWISE_API_TOKEN` and `GASWISE_GOOGLE_ROUTES_ENABLED=true` with an authorized Routes API key. The switch protects all recommendation endpoints. API keys stay server-side. Prefer the economical smart flow below: an authorized Maps website session replaces paid Places discovery, while real driving distances still require Routes. Legacy recommendation queries can make up to 30 candidate route calls and use separate acquisition.

`POST /v1/recommendations` returns purchase/detour/time costs, source evidence and a decision. `best_value` uses conservative observed price bounds; `cheapest_overall` uses selected nominal quotes. Source preference reflects user choice, not verified vendor accuracy. Costs assume fixed gallons and station price for extra fuel; no fill-to-full model, queue/toll/wear cost, or ML prediction is enabled.

Select a vehicle once through `/v1/vehicles/years`, `/makes`, `/models`, `/options`,
or use `POST /v1/vehicles/resolve` with text such as `2018 benz e400`. The resolver asks
remaining body/drivetrain/engine differences and returns the exact vehicle and fuel grade.
Then pass `vehicle_id` to recommendations or smart search. Omit MPG to use EPA combined MPG;
omit `fuel_type` to use the selected vehicle's EPA fuel grade. Details include
city/highway/combined MPG, engine, transmission and drive. EV/PHEV and unsupported
alternative fuels are rejected.
See [vehicle selection API and validation](docs/vehicle-fuel-baseline.md).

`POST /v1/vehicles/vin` accepts a full VIN and optional model year. Official NHTSA
decoding is cross-matched to EPA configuration, MPG and fuel grade; ambiguous or
partial results require confirmation. VIN is sent in POST bodies and successful
responses mask it. See [VIN decoding and validation](docs/vin-selection.md).

`POST /v1/vehicles/plate` connects state/plate → VIN → EPA configuration.
Enable with `GASWISE_PLATE_LOOKUP_ENABLED=true` and select
`GASWISE_PLATE_LOOKUP_SOURCE=autozone` for the anonymous HTTP adapter (no upstream
key). GasWise API authentication remains required. The alternative
`vehicle_databases` source requires its service key and has not been live-tested.
Live AutoZone API validation confirmed 2018 E400 and Coupe via NHTSA; EPA matching
now returns RWD/4MATIC choices with a shared Premium grade; MPG requires configuration confirmation. See [plate source and activation status](docs/plate-selection.md).

Vehicle octane targets now accept higher AKI ratings and support sourced regional
grade estimates with a pump-verified-only option. See [octane matching](docs/octane-matching.md).

Vehicle fuel assessment now attempts bounded public Edmunds/Hertz specification reads by configuration,
with no PDF ingestion or global vehicle database. Existing manufacturer numeric rules take precedence.
Otherwise a labeled US planning estimate uses Regular 87 / Midgrade 89 / Premium 91; it is never
reported as a verified manufacturer minimum. Source availability, configuration matching, grade
agreement and required/recommended distinctions are returned with the estimate. Conflicts require
explicit fuel/AKI selection before ranking. Both public specification sites currently block clean
backend HTTP in the live smoke, so the observed generic-vehicle fallback is explicitly EPA-only.
Set `GASWISE_VEHICLE_SPECIFICATIONS_ENABLED=false` to disable specification reads and category estimates.

Fuel uses `distance_fuel_balance_v1`: actual road distance divided by EPA vehicle MPG, explicit user MPG, or optional
`fuel_cycles` full-to-full same-vehicle records (`distance_miles`, `consumed_gallons`).
Calibration uses total miles / total gallons, not an average of MPG values. Route and baseline
fuel, the MPG used, model basis and assumptions are returned. Smart reranking supports these
records without upstream calls. This estimates aggregate consumption; traffic time is used
for time cost, with no invented grade/weather/traffic fuel correction. See
[model selection and evidence](docs/fuel-consumption-research.md).

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
uv run python ../scripts/tooling/export_openapi.py
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

## Economical smart search

Use `POST /v1/smart/search` to acquire prices once, `/v1/smart/routes` to add routes
without reacquiring prices, and `/v1/smart/rerank` to adjust gallons, MPG, time value
or strategy with zero upstream calls. Current live setup uses Google Maps website
HTTP directions for true road routes and derived costs in `prices_only` mode,
without paid Routes API calls. The signed transaction snapshot expires after 10 minutes.
With the configured Maps session, GasBuddy, Maps and Waze now share one station
inventory. Cash/card conditions must match; unknown payment quotes are excluded
from ranking by default. Four recommendation cards and detailed fuel/time
break-even analysis are computed without additional upstream calls.
Live DTLA acquisition, five GasBuddy address matches and real on-route costs were
verified. See [route evidence and MPG assumptions](docs/google-maps-web-routes.md).
Run the bounded diagnostic from `backend`:

```sh
uv run python ../scripts/smoke/smoke_smart_search.py --routes --trip-mode on_route --maps-detail-limit 0
```

See [request flow, limits and validation](docs/smart-search.md). Existing recommendations
and SSE retain their old acquisition behavior; use the new flow for quota-conscious work.

### Google Maps 網頁 HTTP 查價

`POST /v1/sources/google-maps-web/prices` 不需 Google API key，以單次 HTTP 搜尋取得加油站座標與網頁油價。已驗證使用授權 session，以單次 HTTP 搜尋取得 Premium 等可用油種與更新時間，`all_prices` 可供本地切換油種。匿名模式仍可取得 Regular 摘要；缺漏油種不替換成 Regular。使用方式與限制見 [文件](docs/google-maps-web.md)。

Parts fitment: `POST /v1/parts/fitment` dynamically identifies Amazon brand/MPN/model, discovers exact AutoZone SKUs and checks VIN-derived supplier vehicle configuration. O’Reilly and manufacturer applications provide supplementary evidence with explicit unavailable/conditional states. See [parts fitment scope and live evidence](docs/parts-fitment.md).

Public vehicle specifications now default to pure HTTP curl transport. Live Hertz + EPA agreement was verified for 2021 Camry 2.5L; Edmunds dynamic public JSON is also verified for 2021 Camry, X3 and M4 without cookies, login or API keys. Reproduce from backend: `uv run python ../scripts/smoke/smoke_public_specifications.py`. See [transport evidence and scope](docs/octane-matching.md).

## Service structure and extension

The backend separates domain contracts, HTTP routers, application logic and provider construction. See [architecture and extension guide](docs/service-architecture.md) for provider registration, dependency injection, resource ownership and validation. Existing `/v1` routes and payloads remain compatible.

Script commands and prerequisites are listed in the [categorized script index](scripts/README.md).

## TOP TIER brand badges

Stations from TOP TIER licensed brands (an automaker-run detergent standard above the EPA minimum, not a government rating) carry `top_tier_brand`; `top_tier_only` filters to them during rerank. The brand list refreshes weekly in the background from the official table, with a cached and a bundled fallback. See [TOP TIER design and limits](docs/top-tier.md).

## Docker / GitHub Container Registry

```sh
cp docker.env.example .env
# Set a private GASWISE_API_TOKEN in .env.
docker compose up -d --build --wait
```

Open http://localhost:8080. Pushes to `main` automatically test and publish frontend/backend images to GHCR for Linux AMD64 and ARM64. See [Docker setup and live-provider credentials](docs/docker.md).
