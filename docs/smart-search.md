# Smart search without repeated provider calls

Optional `vehicle_id` selects an EPA vehicle baseline without manual MPG or tank
records. The server resolves the vehicle before price acquisition and signs it into
`snapshot.vehicle`; reranking reuses it with zero catalog calls. `options.mpg:null`
restores the EPA baseline after an explicit MPG override. Vehicle ID changes require
a new search. See [vehicle API](vehicle-fuel-baseline.md).

Three authenticated POST endpoints separate acquisition, routing and arithmetic:

1. `/v1/smart/search`: acquire one transaction's prices and station inventory.
2. `/v1/smart/routes`: optionally add a bounded set of real routes to that snapshot.
3. `/v1/smart/rerank`: recompute costs using the signed snapshot, with **zero upstream calls**.

Current live configuration supports all three stages using Google Maps website
HTTP directions with `GASWISE_MAPS_WEB_ROUTES_ENABLED=true`, including `prices_only`
mode and without paid Routes API calls. See [website route evidence and limits](google-maps-web-routes.md).
The independent paid option still requires Google mode, an authorized Routes API
key and `GASWISE_GOOGLE_ROUTES_ENABLED=true`. No Cloud API/key permission was expanded.
When neither live router is enabled, route requests return 503 before acquisition.
Demo mode can exercise all three stages without live quota.
This workspace has no frontend. The routing switch now also protects the legacy
recommendation/SSE endpoints; their acquisition behavior remains separate from this flow.

## Acquire once

```json
{"origin":{"lat":34.0522,"lng":-118.2437},"radius_meters":5000,"fuel_type":"premium","gallons":"10","mpg":"20","calculate_routes":false}
```

The response contains `snapshot`, `signature`, `ranking` and `upstream_calls`.
GasBuddy discovery uses its raw `GasBuddySearch` contract, supporting GPS without a
mandatory ZIP. It supplies up to 10 quotes from the fetched page and lacks verified
coordinates. Waze adds up to 20 normalized quotes when enabled.

When `GASWISE_MAPS_WEB_SESSION_FILE` is configured in live mode, one authorized
Maps website search supplies prices and up to 20 station identities, including
stations without the requested fuel. This inventory is returned in `snapshot.inventory`.
GasBuddy matches only an unambiguous full street/city/state/ZIP address; punctuation
and ZIP+4 versus ZIP5 normalize, but street aliases and missing directions do not.
Waze crosswalks additionally require coordinates within 75 meters and use the matched
inventory location for route reuse. Duplicate-address identities remain unmatched.
GasBuddy, Maps and Waze evidence is retained separately for a matched station.

`maps_detail_limit` defaults to **0** (maximum 5): no detail lookup unless explicitly
requested. No paid Nearby, Text Search, Places Details or automatic paid fallback is
performed in this inventory mode, including after a website/session failure.

Without a Maps session, an explicitly configured official Google key retains the
existing one-Nearby flow. Street, city, state, ZIP and US-country checks must yield
one unique place. Dated usable GasBuddy prices are preferred; same-response Google
prices fill gaps. Neither flow invents positions: unmatched quotes stay in
`unlocated_gasbuddy`. Discovery is a partial origin-radius sample. Source failures
preserve successful sources and raw quotes; all-source failure raises an explicit error.

Cash and credit are strict eligibility conditions, with no substitution between
them. `allow_unknown_payment=false` excludes unverified Maps/Waze payment conditions
from route acquisition and ranking while retaining them in the snapshot. Explicit
`true` enables an approximate comparison and warning, without treating unknown
conditions as corroboration of known cash/card prices. Numeric Premium 91 also
requires verified octane; a generic Premium label is insufficient.

`upstream_calls` records provider operation attempts, not billable charges or all
HTTP exchanges: GasBuddy cold-start also fetches its public homepage. Successful
price acquisition with the Maps inventory reports GasBuddy=1, Maps search=1,
Waze=1, Nearby=0, Text Search=0 and Routes=0. Detail attempts have a separate
`google_maps_web_details` counter. Demo reports zero external attempts.

## Add routes without refetching prices

POST `/v1/smart/routes` with the exact returned `snapshot`, `signature`, and optional
`route_limit` (default 5, maximum 100). Routes cover origin → station → origin for a
round trip, or origin → station → destination minus origin → destination for an
on-route trip. A baseline is fetched only for on-route trips. Up to the route limit
of candidate calls are made sequentially, without retry; the shortlist mixes nearby
and cheap eligible stations. An existing routed snapshot is reused without new calls.
To select a different route shortlist, start a new transaction explicitly.

This is best **among the routed shortlist**, not a global optimum. Candidate
locations outside the origin-radius or failing initial eligibility are not routed.
Later widening membership/freshness eligibility cannot add routes automatically.
Full route-corridor discovery and traffic refresh are not implemented.

## Recalculate without any provider calls

POST `/v1/smart/rerank`:

```json
{"snapshot":"USE_THE_RETURNED_OBJECT","signature":"USE_THE_RETURNED_SIGNATURE","options":{"gallons":"15","mpg":"25","strategy":"best_value","time_value_per_hour":"20"}}
```

The placeholder for `snapshot` above must be replaced with the actual JSON object.
Omitted options preserve the original search settings. Supported changes include
gallons, MPG, hourly time value, memberships, payment eligibility, required octane,
source preference, maximum price age, stop duration, result count and strategy.
Origin, destination, fuel type, radius and trip mode cannot change in this endpoint.
Payment changes only filter originally collected quotes; newly selecting cash does
not retrieve missing cash prices. Quotes without routes cannot enter true-cost ranking.
`opening_policy` filters closed stations (default `exclude_closed`); see
[opening status](backend-design.md#opening-status).
Brand filtering, full-tank fuel balance and ML predictions are not implemented.

`ranking.recommendations` includes four strategy cards computed from the same routed
snapshot, including winners outside the truncated `ranking.results` list. Round-trip
requests return an unavailable On My Route card. Each ranked result also includes
`break_even` with its reference station, separate fuel/time thresholds and savings
for the requested gallons. Reranking changes both cards and break-even arithmetic
without reacquiring prices or routes. See [cost model](backend-design.md#cost-model).

HMAC signatures reject modified price/route data, including changed expiry. The signature covers a canonical JSON form (sorted keys, integral floats as integers), so a browser JSON round trip, which turns an untyped `3.0` into `3` and reorders integer-like keys, still verifies. Snapshots
expire after 10 minutes and after process restart because the signing secret is
process-local. Keep the snapshot only for the active transaction; don't write it to
localStorage, a database or an oil-price archive. No server-side completed-response
cache or price history is created. Responses use `Cache-Control: no-store`.
Display original collection/source timestamps; reranking is not a refresh. Production
multi-worker use requires an explicitly managed shared signing secret and user/session
ownership; current authentication is the existing private service token.

## Call discipline

Identical concurrent searches and route requests coalesce while in flight. Completed
searches are not cached: a new stage-1 request explicitly refreshes and consumes
quota. If all waiters cancel, outstanding work is cancelled; already sent upstream
requests cannot be undone. Frontends should disable duplicate submissions, require
explicit refresh, and avoid GPS-jitter searches, background polling and SSE.

Cloud currently caps Nearby Search at 30/day and other Places methods at zero.
This limits this project, not shared billing-account SKU usage. No monthly free
allowance or zero-charge guarantee is inferred from the response counters.

Validation uses mocked provider responses and synthetic routes only. It covers
one-Nearby address matching, quota failure, preservation of unlocated quotes,
concurrent-click merging, bounded route acquisition, unchanged settings on partial
rerank, changed winners, zero-call recalculation, signature/expiry checks and auth.
Mocked tests cover the three-source crosswalk, strict payment gates, ZIP+4,
ambiguous identities, Waze proximity, source degradation, shared candidate routes,
zero-call reranking and routing-switch guards for all recommendation endpoints.

## Live acceptance on 2026-10-10

One final 5 km DTLA Premium/credit smoke returned HTTP 200 with all three sources
`ok`: 13 Maps quotes, 20 Waze quotes, 5 located GasBuddy quotes and 4 unlocated
GasBuddy quotes. Of 38 located quotes, 33 had unverified payment conditions, 2
were stale and 3 passed default eligibility. Five GasBuddy crosswalks were verified
against this inventory; no guesses were used for ambiguous/missing directions.
This demonstrates real acquisition and address matching, not pump-price accuracy,
Waze crosswalk coverage or live route acceptance.

The final smoke attempted one search per source, zero Maps details, zero official
Google price/location calls and zero Routes. No price history was saved.

Reproduce deliberately from `backend` (each invocation refreshes live prices):

```sh
uv run python ../scripts/smoke/smoke_smart_search.py --maps-detail-limit 0
```

`--diagnose-matches` prints public unmatched/inventory addresses, never credentials
or pump-price history. `--routes` requires an enabled website or paid router and
limits the smoke to two candidate route calls. `--trip-mode on_route` adds one
baseline route. It exits before source calls if routing is unconfigured. Website
routes and derived costs are now live-verified; see [acceptance](google-maps-web-routes.md).


### Bounded initial routes with geometric fallback

The frontend requests 20 precise station routes and sets `estimate_unrouted_routes=true`.
When this option is enabled, the initial search caps precise station routes at 20
even if a larger limit is requested. On-route searches also require one direct
baseline route. The shortlist mixes nearby stations with candidates ranked through
the existing cost calculation using estimated routes; payment, membership, fuel,
cashback, and vehicle rules still apply.

Other eligible stations remain in comparison using straight-line extra distance
multiplied by 1.3 and a 25 mph speed assumption. For on-route searches, this extra
distance and time are added to the provider's direct baseline. These assumptions
are not calibrated against live road or traffic observations. Their routes carry
`source=straight_line_estimate` and `duration_basis=geometric_estimate`; the UI labels
estimated drive and cost, and decisions involving estimates remain uncertain.

Coverage separates `routed` (precise) from `estimated`. The frontend's compared
count includes both. Explicit `/v1/smart/routes` expansion can calculate up to 100
precise routes using the held prices; reranking makes no upstream calls. Clients
that omit the new flag retain the prior precise-only behavior.

Shared cross-user PostgreSQL pricing reuse, refresh leases, 72-hour quote retention,
and provider request budgets are described in [shared-pricing-cache.md](shared-pricing-cache.md).
