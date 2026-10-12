# GasWise backend design

## Boundaries

`contracts/` owns domain input/output schemas. `api/` owns HTTP adapters, authentication and execution policy. `app/` owns settings, composition and lifetime. `domain/` owns pricing, fuel and vehicle rules; `services/` coordinates workflows. `providers/` is grouped by source and transport. Source and test modules are classified by responsibility and domain; see the [package structure and extension guide](service-architecture.md). Frontend code consumes `/v1` and the exported OpenAPI contract.

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

Google Maps website directions now supply verified numeric road distance and
estimated time in live `prices_only` mode via an independent routing switch.
See [HTTP route provider and evidence](google-maps-web-routes.md). Cost rows expose
the user MPG and estimated detour gallons; these are fuel estimates, not vehicle
telemetry. Route source, time basis and collection time are preserved in snapshots.

Every response includes `recommendations` for all four strategies, computed from the same eligible routed candidates before `max_results` truncation, with no additional provider calls. Each card contains its station identity, costs and decision evidence. `on_my_route` is unavailable for round trips (`requires_on_route_trip`); no eligible candidates return empty cards. Station keys disambiguate provider station IDs. Best Value uses observed comparable price bounds plus time cost; it is a conservative deterministic rule, not an ML score.

Each ranked station includes `break_even` relative to the fastest eligible routed candidate (ties use actual fuel cost then station key). It identifies the reference station and reports per-gallon savings, additional fuel/time cost, fuel-only and time-inclusive thresholds, savings for the requested gallons, and whether each saving is strictly positive. Thresholds use full precision: max(0, additional overhead) / per-gallon savings. A null threshold means this station has no cheaper pump price; explicit savings still describe the current comparison. Zero means no positive minimum volume is needed, while exact equality is a tie, not a saving. These are nominal-price comparisons, not guarantees under conflicting quotes or tank capacity limits.

Ordering and break-even decisions use unrounded costs. Only displayed money rounds half-up to cents; full-precision gallon thresholds are serialized as decimal strings. The legacy `break_even_gallons_vs_nearest` remains a two-decimal convenience field (including time for best_value), now also derived before rounding costs. In the DTLA example Arco's fuel-only threshold against Chevron is 6.2095 gallons, displayed as 6.21, instead of the old rounding-distorted 6.23.

## Freshness and eligibility

`price_updated_at` is the source timestamp; `fetched_at` is the retrieval time. Refreshing does not reset price age. Fresh ≤60 minutes; aging ≤360; stale otherwise; unknown if absent. This is a freshness indicator, not an ML confidence score. Source agreement and purchase-condition evidence now complement it; see the multi-source design below. Prices older than the caller's maximum are excluded; unknown timestamps remain explicitly unknown. Timestamps more than 5 minutes in the future are excluded.

Exact octane requests exclude unverified octane. Costco and Sam's Club membership are conservatively inferred from names in Google, Maps and Waze adapters; this is not comprehensive membership validation. Cash and credit must match exactly. Unknown payment conditions are excluded by default, and may be explicitly allowed with `allow_unknown_payment=true` and a warning; they cannot corroborate known payment conditions. Source coverage can return zero candidates. Individual failed routes are omitted with warnings; failure of discovery or baseline fails the request.

### Opening status

`Station.open_now` and `business_status` are evaluated at retrieval time. Sources:
Google Maps website search labels (observed field 203, `hl=en`, for example
`Open 24 hours` or `Closed · Opens 6 AM`), Waze weekly hours plus Google business
status, and official Places `currentOpeningHours.openNow` / `businessStatus`
(within the Enterprise + Atmosphere SKU `fuelOptions` already triggers). GasBuddy
quotes and Waze crosswalks inherit the matched Maps inventory status, because search
cards often lack the requested grade.

Opening status belongs to the station, not to a quote. `opening_policy` (a ranking
option, so rerank can change it):

| Policy | Closed | Unknown hours |
| --- | --- | --- |
| `exclude_closed` (default) | excluded as `station_closed` | kept, with a warning |
| `require_open` | excluded | excluded as `opening_status_unknown` |
| `ignore` | kept | kept |

Any in-place source reporting closed, or a temporarily/permanently closed business,
excludes every quote of that station; a crosswalk record more than 75 m away cannot.
Closed stations are excluded before the route shortlist, so they consume no route
calls; switching to `ignore` on rerank cannot add routes. The status is not
re-evaluated during the 10-minute snapshot, and it is a listing label, not
pump-level availability. Live check on 2026-10-11 02:36 PDT: 18 DTLA stations
parsed as `Open 24 hours`; 17 Irvine-area Costco stations parsed as closed.

## Updates and resource limits

SSE uses a POST body so location and user choices need not enter URL logs. Browser clients use `fetch` streaming rather than native `EventSource` (which cannot POST or set bearer headers). Events: `snapshot` contains SearchResult; `error` contains code/status and closes; `end` closes after the bounded session. No silent demo fallback in Google mode. Disconnect cancels the generator. Keepalive comments support proxies; disable proxy buffering and set proxy idle timeout above 15 seconds.

At most two searches run concurrently per process by default. Upstream timeout is 15 seconds per request, total search budget 55 seconds, Google calls make one attempt without automatic retries. Excess concurrency returns 429 with Retry-After. These limits are per-process, not a distributed rate limiter or daily budget. Use one worker locally; production needs a gateway and provider quota enforcement. SSE connections do not continuously hold a search slot.

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

Smart search now separates discovery, bounded route acquisition and zero-call reranking. See [smart search](smart-search.md). The original recommendations/SSE still reacquire data.
