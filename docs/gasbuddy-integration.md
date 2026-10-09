# GasBuddy and multi-source comparison — 0.5

## Verified default: no browser

The production default is `http` transport. A new httpx HTTP/2 client requests `https://www.gasbuddy.com/`, obtains the server-provided `window.gbcsrf` token and that response's anonymous cookies, and sends the normal `SearchPrices` GraphQL query with those credentials. The query also requests station name, address and price unit, so the challenged search HTML is not needed for station metadata.

This local flow has been verified with an initially empty cookie jar, without Chrome, browser cookies, JavaScript execution or Playwright imports. It is an observed anonymous website API, not an official commercial API partnership. If a future response rejects access or presents a challenge, the source returns an explicit error; no browser fallback or challenge solver runs automatically.

| Step | Verified result |
| --- | --- |
| Homepage via ordinary HTTP/2 | HTTP 200, CSRF token and anonymous cookies |
| SearchPrices with that session | HTTP 200, seven station records including metadata |
| Premium / credit normalization | Four valid prices with original source timestamps |
| Cold FastAPI check with Playwright imports forbidden | HTTP 200, four quotes, 1.071 seconds |
| Subsequent HTTP query in the same process | HTTP 200, four quotes, 0.244 seconds |

These are local measurements, not a latency or coverage guarantee. Unit/API tests cover existing ranking behavior and session bootstrap, cookie persistence, new prices on every query, expiry, idle eviction, source failure and cleanup.

## Why the original route failed

The supplied [90015 Premium / credit page](https://www.gasbuddy.com/home?search=90015&fuel=3&method=credit&maxAge=0) works through normal browser rendering. Its `maxAge=0` filter means **No Limit**, not a fresh-price requirement. Direct clean requests to that search page returned `cf-mitigated: challenge` in tests using HTTP/1.1, HTTP/2, normal landing-then-search navigation, Node HTTP and system curl.

The public homepage, however, supplied an anonymous CSRF token through standard HTTP. That token and its cookie jar were accepted by the existing anonymous SearchPrices API. This establishes the working route; it does not identify every server-side Cloudflare rule. [Cloudflare documents the challenge response header](https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/).

Observed signed-out requests used `gbcsrf` rather than `Authorization: Bearer`. The token is initially provided in HTML, not guessed or synthesized. Cookies and tokens remain opaque, private to each source HTTP client, and are never printed or persisted to disk by the production provider. No logged-in user session is used.

## Backend separation

`providers/http_session.py` owns HTTP sessions and source payloads. `providers/gasbuddy_web.py` normalizes quotes and payment conditions. `comparison.py` owns source evidence and selection; `service.py` owns route costs and rankings. The frontend will only consume versioned HTTP/SSE contracts.

Sessions expire after `GASWISE_GASBUDDY_SESSION_SECONDS` (600 seconds by default), once an in-flight query completes. Idle eviction closes the cookie jar and removes the token. Search changes can reuse the same site session, while every API query requests new price/metadata data. Prices are not cached or archived. Rejection invalidates the session and returns an error without retrying; a later query can establish a fresh anonymous session normally.

The provider requests the bounded first page of results. Missing/zero fuel prices are omitted. Credit requests never fall back to cash-only prices. For a cash user, an ordinary credit price can be used when no cash quote exists. Original `price_updated_at` remains distinct from retrieval time. Numeric octane is unverified; Premium is not a guaranteed 91-octane observation.

## API and local configuration

| Endpoint | Behavior |
| --- | --- |
| `POST /v1/sources/gasbuddy/prices` | Live, normalized website quotes with payment basis and source timestamps |
| `POST /v1/recommendations` | Enabled source comparison and route costs; needs a routing provider |
| `POST /v1/recommendations/stream` | Periodic source/route recalculation; needs a routing provider |
| `GET /v1/capabilities` | Transport, browser requirement, mode and recommendation availability |

Local `.env` selects:

```dotenv
GASWISE_MODE=prices_only
GASWISE_GASBUDDY_WEB_ENABLED=true
GASWISE_GASBUDDY_WEB_TRANSPORT=http
GASWISE_GASBUDDY_SESSION_SECONDS=600
GASWISE_API_TOKEN=<private service token>
```

Website queries need a five-digit `postal_code`. No arbitrary source URL is accepted. Use [gasbuddy-search-example.json](../contracts/gasbuddy-search-example.json). The API requires the local bearer service token; that authenticates callers to **GasWise**, while the external GasBuddy request uses its anonymous CSRF/cookie session.

`prices_only` returns real prices and responds `503 routing_provider_not_configured` for route recommendations. Google credentials are not needed for raw prices. For full cost ranking, set `GASWISE_MODE=google` with a Google key; address resolution verifies street number/street/city/state/ZIP before assigning a Google place ID and GPS. No synthetic route or cost is presented as live. Google routing/coverage remains unverified without credentials.

From `backend`:

```sh
uv run python ../scripts/check_live_gasbuddy.py --repeat 3
uv run python ../scripts/check_no_browser_runtime.py
```

The first checks the running HTTP service. The second creates an independent FastAPI lifespan with an empty cookie jar and explicitly forbids Playwright imports, proving a cold start needs no browser. Both scripts print statuses, timing and quote data without exposing credentials. The protocol diagnosis helper `probe_gasbuddy_browserless.py` is for development and uses optional development tools; it is not part of the production request path.

Production dependencies exclude Playwright and Chrome:

```sh
uv sync --locked --no-dev
uv run --no-dev uvicorn gaswise.main:app --host 127.0.0.1 --port 8000
```

## Source evidence and decisions

Only explicit canonical IDs / verified full-address mapping join stations. Brand names or nearby coordinates are insufficient. A canonical match with coordinates differing by over 75 meters is excluded.

Eligibility filters grade, exact octane when requested, radius, membership, applicable payment basis, report age and implausibly future timestamps. Missing source time remains unknown. `excluded_count` counts rejected quotes and failed routes, not unique stations; upstream missing prices are not included.

Selection considers known-time quotes within 30 minutes of the newest report. Verified payment takes precedence, then user `preferred_sources` (GasBuddy first by default), then recency. Preference is not measured source accuracy. All evidence is preserved; different cash/credit, octane or membership conditions are marked noncomparable.

For matching purchase conditions, the newest quote from each source participates in comparison. Spread ≤ $0.05/gal is consistent; greater spread is conflicting. Corroborated quality requires two or more comparable sources with known payment and report times within 60 minutes. Unknown conditions, old reports or conflicting prices remain limited/disputed. Two vendors can share upstream data, so agreement does not establish independence or accuracy.

Observed price minima/maxima produce trip-cost scenario ranges, not statistical confidence intervals. Best Value ranks by maximum observed generalized cost; Cheapest Overall uses the selected nominal quote; Fastest Stop uses estimated travel time. The decision is robust only among retrieved candidates when fresh comparable ranges preserve the winner; otherwise uncertain/single_source/no_eligible_stations explains the limitation. At most 30 merged candidates are routed, and results are bounded by `max_results`. Candidate search is first-page/origin-radius, not exhaustive route-corridor discovery.

## Optional older transports and contracted feed

`browser` and `session_http` remain explicit optional alternatives for diagnostics. They are not imported by the default HTTP service. To use them, install `uv sync --extra browser` and configure a suitable browser runtime. The production HTTP mode never automatically switches to them.

A contracted feed may be configured with `GASWISE_GASBUDDY_FEED_URL` and `GASWISE_GASBUDDY_FEED_TOKEN`. This is a GasWise-owned normalized adapter, not the website GraphQL URL. It accepts schema `gaswise.gasbuddy-feed.v1`, at most 100 Station records, `source=gasbuddy`, explicit canonical IDs when verified, timezone-aware timestamps, HTTPS and a feed token. No contracted feed has been configured/live-tested; the real supplier translator still needs supplier documentation/credentials. No historical storage or prediction model is enabled.


## Search filters (2026-10-09)

`POST /v1/sources/gasbuddy/prices` now uses a dedicated `GasBuddySearch` request.
Provide `search` (city/region or ZIP), legacy `postal_code`, or GPS `origin`.
City/ZIP lookups do not require GPS. Street-address geocoding is not guaranteed.
Fuel: regular, midgrade, premium, diesel. Payment: cash, credit, cash_or_credit.
The last option chooses the lower available quote per station and reports its actual
payment basis. Cash retains credit fallback when no cash price is reported.
Optional `brand_id` forwards GasBuddy's numeric ID; omitting it includes all brands.
Brand names/IDs are exposed at `GET /v1/sources/gasbuddy/brands`. `max_price_age_minutes: null` means
No Limit; a number excludes old, unknown or future-dated reports locally, based on
source timestamps. The upstream maxAge remains 0 to avoid unverified unit conversions.
Filters apply to the bounded first page; an empty result does not prove no matching
stations exist. Recommendation requests still use the separate `Search` model with
mandatory origin and cash/credit only; cash_or_credit is a browsing comparison mode.

Example:
```json
{"search":"Los Angeles, CA","fuel_type":"premium","payment_type":"cash_or_credit","max_price_age_minutes":null,"max_results":10}
```

Live verification: city query returned five actual quotes with cash/credit labels;
ZIP with a 60-minute limit returned zero eligible quotes. Verified brand IDs returned Chevron (9 quotes), Shell (10), ARCO (10), Costco (4).


## Brand dropdown

`GET /v1/sources/gasbuddy/brands` uses the same bearer authorization as prices.
The response includes `all_brands` (brand_id null), 26 alphabetical `brands`
(name, brand_id, slug), verified_on, source_url, and exhaustive=false.
Mappings were extracted from the public GasBuddy client bundle, not inferred
from station names. Omit brand_id or send null to search all station brands.
Unknown positive IDs remain accepted for compatibility with future upstream brands.
This list also includes brands operating outside the US; listing a brand does not
guarantee nearby US stations or eligible fuel quotes. Station display names can
be different from the selected fuel brand (e.g. Shell query includes C.T. Truck Stop).

```json
{"search":"Los Angeles, CA","fuel_type":"premium","payment_type":"credit","brand_id":31,"max_results":10}
```


## Costco omission fix

Process all station records in the fetched page, filter valid fuel/payment/age quotes,
then sort by price and apply max_results. Previously slicing station records before
filtering omitted Costco and wasted result slots on stations without prices.
Raw Costco quotes now include membership_required="costco"; rankings retain the
existing membership eligibility checks. ZIP 90015 upstream has no Costco results;
Los Angeles city search and brand_id=38 do return Costco. Remaining upstream pages
are still not exhausted, and partial stays explicit. Costco is not always cheapest.
