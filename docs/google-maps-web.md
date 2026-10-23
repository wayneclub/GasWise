# Google Maps website HTTP prices

`POST /v1/sources/google-maps-web/prices` uses Google Maps website HTTP requests. The endpoint requires the GasWise bearer token and uses no Places API key or browser at runtime.

```json
{
  "origin": {"lat": 34.0347, "lng": -118.2611},
  "fuel_type": "premium",
  "radius_meters": 5000,
  "max_results": 20,
  "detail_limit": 0
}
```

The response includes:

- `stations`: quotes matching the requested fuel.
- `all_prices`: every available fuel quote from the same result, so callers can change fuel locally without another search.
- `inventory`: station names, coordinates, address, straight-line distance and available fuel types.
- `authentication`: anonymous or session (configuration mode, not an account-validation guarantee).
- `upstream_http_requests`, `detail_requests`, `official_api_requests`: attempted website request counts; official API requests are always zero in this provider.

Search returns a bounded sample, not an exhaustive inventory. Radius is enforced with a straight-line distance filter after discovery; `max_results` limits candidates including candidates without prices. No routing is performed.

## Verified session behavior

On 2026-10-10, the same place URL was tested from the same browser with and without login credentials. Omitting credentials produced no complete fuel table; retaining the existing Google session produced Regular, Midgrade, Premium and Diesel with timestamps. After explicit user authorization, the session was saved privately and a backend `httpx` request retrieved the same four grades. An authenticated nearby search also returned full fuel tables directly, without a detail request.

The running FastAPI endpoint was verified with a 5 km DTLA Premium query, `max_results=20`, `detail_limit=0`: HTTP 200, 17 candidates, 12 Premium quotes and 41 total fuel quotes across all four grades. It made one website request, zero detail requests and zero official API requests. Returned Premium quotes included update timestamps.

Anonymous operation remains available for Regular summaries. Full fuel coverage is not guaranteed even with a session. Premium never substitutes Regular and does not prove 91 octane. Payment type remains unknown. Summary quotes lacking an update timestamp keep `price_updated_at=null`; `fetched_at` is retrieval time, not a price update.

## Request budget

`detail_limit` defaults to **0**. A normal query makes **one search request** and returns all available fuel grades. There are no retries, polling, pagination, browser fallback or paid API fallback.

Explicitly setting `detail_limit` (0–10) allows bounded place-detail requests for missing non-Regular prices among returned candidates. One request runs alone first so a rejected session ends enrichment immediately; the remaining candidates run in bursts of four. Already priced stations are skipped; any provider error stops later bursts. The response preserves discovered inventory and warns about failures. An identity mismatch never assigns another station's prices. Regular queries use search data only.

## Private session configuration

```text
GASWISE_MAPS_WEB_SESSION_FILE=/absolute/private/path/google-maps-http-session.json
```

The authorized local session is currently outside the repository at `~/.config/gaswise/google-maps-http-session.json`, with mode **0600**. The file contains Google login credentials; do not publish it, copy it into source control or share it. No credential values are placed in logs, API responses or documentation. Capture/refresh requires explicit user authorization; the backend does not scrape credentials from browsers.

File format:

```json
{
  "captured_at": "2026-10-10T00:00:00Z",
  "cookies": [
    {"name": "SID", "value": "REDACTED", "domain": ".google.com", "path": "/", "expires": -1}
  ]
}
```

This redacted example is not a functional session. Real sessions can need several related Google cookies; the nine-cookie subset tested in this investigation did not produce the complete table, while the complete authorized session did.

Only `.google.com`/`www.google.com` cookies with `/` paths are used. Expired cookies are skipped. Missing, unsafe, nonprivate or symlink session files fail before any website request. Cookies are sent only to fixed HTTPS `www.google.com` search/detail endpoints. Redirects are not followed. A dedicated client isolates this source from other providers. No automatic login, credential refresh, challenge solving or access-protection bypass is implemented.

Google can revoke sessions before their recorded expiry. Rejections and malformed/challenge responses fail explicitly; a reduced HTTP 200 can instead leave prices missing, so configuration alone is not proof of a valid login. Responses use `Cache-Control: no-store`; no fuel-price history is persisted. Unset the session-file setting to return to anonymous operation.

## Parsing and references

[Official FuelOptions / FuelPrice semantics](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places#FuelOptions) define type, price and update time. The website uses a different array protocol: observed station field **86** is the complete fuel table and field **88** is the search summary. Numeric fuel kind and label must agree: Diesel=1, Regular=3, Midgrade=4, Premium=5. These are observed website values, not an official API ordinal guarantee.

Fuel-row fields: index 2 is Unix seconds, index 3 must be `gallon`, index 5 must be `USD`, index 6 is the numeric price, and index 7 is the fuel label. Price is converted to Decimal and update time to UTC. Malformed/nonfinite/nonpositive/conflicting fuel rows are skipped independently. A sanitized observed station fixture covers all four grades.

The request structure was also compared with the author's [HTTP scraper request definitions](https://github.com/sonagara-vashram/google-maps-scraper/blob/main/google_maps_scraper/constants.py). Runtime uses `httpx`; no third-party scraper code, browser impersonation dependency, proxy rotation or retry loop was installed into GasWise.

This undocumented protocol can change. The standalone endpoint remains available.
In live mode, configuring the authorized session also selects this source as the
smart-search inventory, replacing paid Nearby discovery with one website search.
Smart detail enrichment defaults to zero and is explicitly bounded by
`maps_detail_limit` (0–5). Session failure never falls back to paid Places calls.
See [three-source search and live acceptance](smart-search.md).

## Rounded prices and payment terms

A 2026-10-15 Fastrip photo comparison at 1400 Valinda Ave shows Maps Regular
$5.86, Midgrade $6.06 and Diesel $8.00 consistent with rounded card prices
$5.859/$6.059/$7.999, while Premium $6.04 is consistent with rounded cash
$6.039, rather than card $6.159. The photos establish this example, not a
universal Google policy or a synchronized provider API replay.

Every Google fuel quote retains `payment_type=unknown` and the original numeric
price. Never inherit payment terms from another grade or recover a guessed third
decimal. Fresh same-station/same-grade payment evidence within 30 minutes may
support an inference. Cent-valued Google quotes must equal a peer price rounded
with decimal half-up rounding; a mere difference under one cent is insufficient.
If distinct cash and card prices round to the same Maps price, payment remains
unresolved. An inference does not overwrite raw payment terms or verify the pump.
The UI explains this uncertainty; estimates using a payment markup are labeled
as based on a payment assumption.
