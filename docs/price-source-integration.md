# Adding independent fuel-price services

GasWise owns aggregation, source comparison and routing costs. Each upstream service
owns retrieval and normalization. Frontend clients keep using GasWise APIs.

## Configuration-only integration

Set `GASWISE_PRICE_SOURCES` to a JSON array in backend `.env`:

```dotenv
GASWISE_PRICE_SOURCES='[{"source_id":"partner_prices","url":"https://prices.example.com/v1/stations","token":"REPLACE_WITH_SERVICE_TOKEN","enabled":true,"timeout_seconds":15}]'
```

Restart after configuration changes. URLs are fixed at startup, never submitted by
frontend users. HTTPS is required; each token is used only for its own configured
endpoint. IDs must be unique and cannot reuse built-in IDs. Disabled entries appear
as not_configured. Discovery excludes URLs and secrets. Do not mix live feeds into
demo mode. `prices_only` can run with feeds and no GasBuddy or router; `google` mode
adds the same feeds to existing source comparison and route-cost ranking.

## Upstream request and response

GasWise sends POST with the existing normalized `Search` request (origin GPS,
fuel/payment, quantity, route settings and freshness rules). Authentication is
Bearer when a token is configured. City/ZIP browsing via the existing GasBuddy
endpoint retains its separate request contract; the generic normalized endpoint
requires GPS and accepts cash/credit, not cash_or_credit.

The service returns:

```json
{
  "schema_version": "gaswise.price-feed.v1",
  "stations": [{
    "id": "upstream-station-123",
    "name": "Example Fuel",
    "address": "123 Main St, Los Angeles, CA 90015",
    "location": {"lat": 34.04, "lng": -118.27},
    "price_per_gallon": "5.79",
    "currency": "USD",
    "unit": "US_gallon",
    "fuel_type": "premium",
    "octane": null,
    "payment_type": "credit",
    "price_updated_at": "2026-10-09T20:00:00Z",
    "fetched_at": "2026-10-09T20:01:00Z",
    "source": "partner_prices"
  }]
}
```

Formal contract: `contracts/price-feed.schema.json`. At most 100 records per feed
response; invalid records reject that source response instead of inventing values.
Use actual source timestamps; unknown price_updated_at/octane stay null. Coordinates
must be actual station coordinates. Never infer canonical identity from brand or
proximity; only add canonical_id using a verified shared identity crosswalk.
Source must exactly equal the configured source_id. HTTP failures, schema failures,
provenance mismatches, adapter exceptions and timeouts are isolated per source.
Caller cancellation still propagates. No retry or price cache is added.

## GasWise endpoints

- GET `/v1/sources`: configured/disabled source inventory and timeout limits. This
  describes configuration, not upstream health.
- POST `/v1/prices`: normalized raw station quotes with source_statuses, no routing
  or ranking; duplicates and stale observations remain explicit raw observations.
- POST `/v1/recommendations`: existing eligibility checks, cross-source comparison
  and deterministic route-cost ranking, when a router is configured.
- POST `/v1/sources/gasbuddy/prices`: existing browser-free city/ZIP quote browsing.

In prices_only mode, GasBuddy raw browsing still works, but it cannot join normalized
GPS aggregation without a station locator. Its registry entry explains that boundary.
When every normalized source fails or none is configured, `/v1/prices` returns 502;
it does not silently return demo records. Empty successful feeds are valid.

## In-process adapters

For a different upstream protocol, implement `async stations(query: Search) ->
list[Station]` and register using `SourceRegistry.register(source_id, adapter,
timeout_seconds)`. Own protocol-specific credentials and data conversion inside the
adapter. Native adapters need startup registration; HTTP contract services need only
configuration. Use `ProviderError` with a safe diagnostic code. Routing remains a
separate dependency. Shared HTTP client and session worker close at app shutdown.
