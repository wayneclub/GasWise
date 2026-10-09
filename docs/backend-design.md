# GasWise backend design

## Boundaries

`models.py` owns strict input/output contracts. `providers/` translates external price and route APIs. `comparison.py` owns price evidence, cross-source identity and condition comparison; `service.py` performs cost ranking and decision analysis. `main.py` owns HTTP, authentication, concurrency, timeouts and stream lifecycle. Frontend code will only consume `/v1` and the exported OpenAPI contract.

Provider interfaces accept a search and points, returning normalized stations and routes. HERE/OPIS can be added behind that interface after access, payloads, US premium coverage and retention rights are verified; no guessed HERE endpoint implementation is shipped.

## Cost model

For on-route trips, compare origin → station → destination with origin → destination. Round-trip trips compare origin → station → origin with a zero-distance baseline. Negative differences are clamped to zero. Actual fuel cost = price × purchased gallons + extra miles / MPG × station price. Generalized cost adds (extra drive minutes + stop minutes) / 60 × hourly time value. Queue, toll, wear and differing segment MPG are excluded. Fixed purchased gallons are supported; “fill tank” needs tank capacity/current fuel and a separate fuel balance model.

Strategies:

| Strategy | Ordering |
| --- | --- |
| cheapest_overall | Actual fuel cost, extra drive time |
| fastest_stop | Extra drive time, actual fuel cost |
| best_value | Worst observed comparable generalized trip cost, extra drive time |
| on_my_route | Actual fuel cost among origin-radius candidates with a destination |

Current on-route search adjusts costs correctly, but candidate discovery is an origin-radius search, **not full route-corridor discovery**. Long-distance corridor search is future work. Baseline and candidate calls are not atomic traffic snapshots; the query takes a few seconds and clamps negative detours. Stop duration is a user estimate shared across stations.

Break-even versus the fastest nearby eligible station = additional detour fuel cost / per-gallon savings; best_value also includes additional time cost. Null means no cheaper pump price to compare. It is a continuous threshold, not a guarantee that a particular tank can hold that amount. Money rounds half-up to cents; displayed break-even uses these rounded cost components.

## Freshness and eligibility

`price_updated_at` is the source timestamp; `fetched_at` is the retrieval time. Refreshing does not reset price age. Fresh ≤60 minutes; aging ≤360; stale otherwise; unknown if absent. This is a freshness indicator, not an ML confidence score. Source agreement and purchase-condition evidence now complement it; see the multi-source design below. Prices older than the caller's maximum are excluded; unknown timestamps remain explicitly unknown. Timestamps more than 5 minutes in the future are excluded.

Exact octane requests exclude unverified octane. Costco and Sam's Club membership are conservatively inferred from names in the Google adapter; this is not comprehensive membership validation. Cash/card/discount eligibility is unknown and disclosed. Source coverage can return zero candidates. Individual failed routes are omitted with warnings; failure of discovery or baseline fails the request.

## Updates and resource limits

SSE uses a POST body so location and user choices need not enter URL logs. Browser clients use `fetch` streaming rather than native `EventSource` (which cannot POST or set bearer headers). Events: `snapshot` contains SearchResult; `error` contains code/status and closes; `end` closes after the bounded session. No silent demo fallback in Google mode. Disconnect cancels the generator. Keepalive comments support proxies; disable proxy buffering and set proxy idle timeout above 15 seconds.

At most two searches run concurrently per process by default. Upstream timeout is 15 seconds per request, total search budget 55 seconds, transient retries at most three. Excess concurrency returns 429 with Retry-After. These limits are per-process, not a distributed rate limiter or daily budget. Use one worker locally; production needs a gateway and provider quota enforcement. SSE connections do not continuously hold a search slot.

## Persistence decision

No database is needed for this first stateless backend. Google price/route responses are neither written to disk nor retained between snapshots; HTTP responses use no-store. No background area scraping. PostgreSQL/PostGIS belongs in a later licensed ingestion service with explicit retention policies and migrations, not as an unconditional archive of Google content.

A licensed ingestion design should separate station metadata, price observations (source event time and ingestion time), provider entitlement/retention policy, and refresh-job state. Workers need deduplication, backoff, atomic writes, distributed leases and expiry cleanup before enabling unattended collection. It is intentionally not enabled against Google without confirmed rights.

## Official sources checked on 2026-10-09

- [Places resource / FuelOptions](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places): grade, Money price and updateTime; PREMIUM does not supply numeric octane.
- [Place data fields](https://developers.google.com/maps/documentation/places/web-service/data-fields): fuelOptions is a billed advanced field. Confirm account SKU and quotas before live testing.
- [Routes computeRoutes](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes): distance, duration and intermediate waypoints.
- [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies): storage and attribution requirements. A future frontend must display Google Maps attribution and returned third-party attributions, follow map display rules, and provide the required terms/privacy policy.

## Acceptance boundary

Implemented: independent API, deterministic costs, round-trip/on-route comparison, stream polling, provider adapters, synthetic multi-source demo, bounded requests and contract. GasBuddy has a verified browser-free HTTP path: public homepage CSRF/cookies followed by SearchPrices with station metadata. Direct search-page HTTP requests were challenged. prices_only mode exposes real quotes but disables route recommendations until credentials are supplied. Local automated tests cover math, exclusion, validation, auth, and mocked upstream payloads. Live station accuracy, US Premium 91 coverage, deployment, route-corridor discovery, fill-to-full, historical storage and ML are not verified or implemented.

## Multi-source extension (0.5)

See [GasBuddy and comparison design](gasbuddy-integration.md) for website/feed access state, exact station matching, cash/credit separation, freshness-aware source preference, conservative Best Value ranking, observed cost bounds, source degradation, tests and remaining live verification.

The HTTP-session provider retains a bounded anonymous cookie jar/token for API queries; the frontend remains unaware of session mechanics. Default production mode requires no Chrome or graphical session. Older browser transports are explicitly optional.
