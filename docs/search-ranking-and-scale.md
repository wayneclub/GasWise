# Search, ranking and scale

Implemented 2026-10-12; deployment and live timings are recorded below after validation.

## Current implementation

- Independent GasBuddy, Google Maps viewports and Waze reads run concurrently. Across all requests in one worker, cache loaders allow at most one GasBuddy, two Maps, two Waze and one AAA operation. Routes allow four concurrent reads. Identical in-flight reads have one owner and cancel only when all waiters cancel; successful and failed reads remain distinguishable.
- Maps centres snap to stable geographic query cells with side approximately 10% of the requested radius. The discovery viewport radius is enlarged by 10% to cover the snapped offset. Every returned station is filtered with the exact origin and haversine radius. Longitude spacing accounts for latitude; near poles or the maximum supported radius, discovery keeps exact centres. Station coordinates and route endpoints are never snapped. This increases nearby-user cache sharing without treating ZIP borders as geographic limits.
- Search radius is 2, 5, 10 or 20 miles. ZIP input resolves to a centre point. Five overlapping viewport queries plus bounded address lookups improve coverage. Website listings are capped: discovery is partial, not proof that every station in the circle was found. Viewport expansion affects discovery context, never the final eligibility radius.
- Price caches expire after 90 seconds; route caches after 300 seconds; AAA after six hours. Source rate limits pause queued reads for 30 seconds; known prices can still be read from positive caches. A retry never advances `price_updated_at`, `fetched_at` or AAA's publication date. Closed or expired observations never become eligible because they were cached.
- Response `timings_ms` separates discovery/enrichment, routes plus regional averages, ranking and total. This measures backend elapsed time, not browser/network latency.
- Canonical stations are merged before sorting. Any matched Google permanent/temporary closure excludes that station under the default opening policy, even if GasBuddy still lists its price. Only matching fuel/payment and recent prices are comparable. All category boards use the same signed snapshot and eligible station set.
- Each category returns three distinct canonical stations, or fewer when fewer qualify. Money sorts actual fuel outlay (purchase minus user-estimated card rewards plus detour fuel). Time sorts extra driving minutes, then outlay. Balance sorts the conservative upper comparable cost plus extra driving at the user-set hourly value, then minutes. Existing bounded TOP TIER preference applies to balance only. Whole-precision calculations precede display rounding; stable station keys break ties.
- AAA is context only, never a substitute station quote or ranking input. Match exactly named metro components for parsed cities, otherwise display a clearly labeled state fallback. Preserve fuel grade, state, region, publication date and source URL. Compare the selected pump/comparison price before cashback; AAA's payment basis may differ. There is no public city-level API claim here. See [AAA California averages](https://gasprices.aaa.com/?state=CA).

## Core algorithm

For one fill-up, dynamic programming does not improve this decision: each eligible station is an independent alternative. Compute each cost in O(n), then deterministic category sorting in O(n log n). A size-three heap could reduce ranking to O(n), but network discovery and routing dominate at the current maximum of 100 routed candidates. Prefer reducing duplicate upstream work over micro-optimizing a small sort.

The Pareto frontier of (fuel outlay, extra minutes) explains the tradeoff: a user with time value v minimizes `outlay + minutes * v / 60`, with source-conflict uncertainty and optional TOP TIER preference kept explicit. Do not prune unresolved stations solely on straight-line distance or apparent pump price: actual routes, freshness, payment and conflicts can change the winner. Shared routes allow all category boards and hourly values to be computed without additional provider reads.

For a future multi-stop trip with tank capacity and fuel constraints, use a directed route graph and a discretized state `(route node, remaining fuel)`, transitions for travel and refuel, with constrained shortest path / dynamic programming. Account for capacity, reserve, real route consumption, station hours and price uncertainty; do not reuse the one-stop formula as an unverified multi-stop optimum.

## Multi-worker storage design — not deployed in this change

Current TTL caches, concurrency gates and signed-snapshot secrets are process-local. The 24-user controlled regression verifies coalescing and bounded concurrent routes in one worker; it is not evidence of production throughput or cross-instance coordination. Do not start independent workers and assume those protections remain shared.

Use a separate GasWise database/user on PostgreSQL with PostGIS for a canonical station catalogue and immutable observations. Suggested entities:

| Entity | Key and stored provenance | Index/retention |
|---|---|---|
| stations | canonical id, coordinates, address, provider ids | geography Point GiST; provider id unique |
| price observations | station, source, fuel, payment basis, octane, price, reported_at, retrieved_at | composite latest-observation index; bounded history retention |
| opening observations | station, source, business status, observed_at, hours | source timestamp retained; closure precedence explicit |
| discovery cells | provider, cell, radius/budget, checked_at, expiry, completeness | unique query identity; source-health cooldown |
| regional averages | AAA region, state, grade, publication date, value | unique source/region/grade/date |

Use `ST_DWithin(geography, origin, radius_meters)` to include boundary-near stations efficiently; it supports a spatial-index prefilter. H3 grid disks can schedule coverage jobs and coalesce adjacent searches, but graph ring count is not exact miles; always finish with a geodesic radius filter. References: [PostGIS ST_DWithin](https://postgis.net/docs/ST_DWithin.html), [H3 grid traversal](https://h3geo.org/docs/api/traversal/).

For several replicas, move query cache, provider concurrency/rate limits and single-flight leases into a shared coordinator (Redis or PostgreSQL bounded leases). Share the snapshot HMAC secret securely across replicas. Acquire leases with expiry and ownership-safe release, re-check cache after waiting, and avoid holding a database transaction while making HTTP requests. Keep freshness eligibility evaluated against request time; expired price observations may be displayed as context but cannot silently win recommendations.

Refresh hot cells on demand at the existing budget, retain station catalogue longer than volatile prices, and refresh closures/hours independently. Introduce background queues only with deduplicated jobs, bounded retry/backoff and provider budgets. Measure p50/p95 discovery and routing latency, cache-hit ratio, provider failure rate, eligible/priced/discovered coverage and work per user before increasing worker count. Persistent location, VIN or plate history is unnecessary for this cache design.

## Validation observations

2026-10-12 local live search at the public 90015 centre, Premium, 5-mile radius, three GasBuddy pages, five Maps viewports and five address lookups: 5.777 seconds including 36 discovered / 8 eligible / 8 routed stations. Immediate repeated request took 0.074 seconds, had 21 cache hits and zero upstream requests, and preserved every source report timestamp. These are individual samples, not p95 or a throughput guarantee.

A controlled 50ms fixture comparing the previous `e865a31` acquisition code to this version measured cold search 4.425→0.209 seconds and warm search 4.011→0.003 seconds. Most of that warm difference is removal of unconditional waits; these are synthetic provider timings, not live network performance.

Coordinate-bearing Waze quotes that omit state/direction can merge only with one inventory station agreeing on name, numbered street, city and ZIP, within 25 metres; explicit state/direction conflicts and ambiguous matches are rejected. Address-only GasBuddy quotes still use the strict full-address crosswalk. This prevents repeated physical stations from consuming leaderboard places without brand-only matching.

Production validation (AWS, 2026-10-12): HTTPS returned 200; the narrowly scoped Cloudflare script/connect CSP was present and the browser reported no CSP errors. First full search took 3.439 seconds end-to-end (backend 2606.8ms); repeated search took 1.171 seconds end-to-end (backend 62.2ms), with zero upstream calls and unchanged report timestamps. Cash/hourly-value reranking also used zero upstream calls. These remain single-request samples, not a production load-test claim.

GasBuddy bootstrap and the official AAA page returned 403 from the AWS host. Maps/Waze still produced eligible station rankings; unavailable providers remain visible. AAA worked from the local host, but production does not fabricate a city average when it cannot fetch the official data. A licensed/reliably reachable regional feed or an explicitly dated shared snapshot pipeline would be needed for uninterrupted production benchmarks; none is silently substituted here.


Subsequent direct AWS AAA transport recovery is recorded in [upstream-reachability](upstream-reachability.md). The earlier 403 measurements are historical; GasBuddy remains challenged.
