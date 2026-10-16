# Shared public pricing cache

GasWise uses the existing PostgreSQL 16 service on the production host. It does
not create a PostgreSQL or Redis container. The dedicated `gaswise` database and
`gaswise_cache` login isolate pricing tables from PassBar and other applications.
`db.wayneclub.com` resolves through Cloudflare; backend SQL uses the existing
Docker network's `postgres:5432` endpoint instead of publishing a new port.

## Configuration and lifecycle

Set `GASWISE_DATABASE_URL` privately to enable the shared cache. Leave it empty for
local/demo runs without a database. Startup opens a bounded asyncpg pool and applies
the idempotent schema under a short transaction advisory lock. If a configured
DB is unavailable, startup fails with a sanitized message. Runtime cache/budget
failures never trigger unbudgeted upstream fallback.

Only public GasBuddy, Maps-web and Waze response DTOs are persisted. There are no
visitor accounts, browser identifiers, VINs, plates, vehicle selections, precise
visitor route endpoints, credentials or cookies in these tables. Query keys are
versioned SHA-256 digests of provider query DTOs. Public station coordinates and
fixed discovery query cells remain public pricing observations. Route totals
remain in the existing bounded process-memory cache.

The table definitions ship in `gaswise/providers/storage/schema.sql`:

- `query_cache`: provider response, collection freshness, partial-coverage
  evidence, and a 120-second refresh lease.
- `stations`: source ID, canonical mapping, whitelisted public identity metadata.
- `quotes`: separate source/station/fuel/payment/membership/octane conditions,
  original reported/fetched times, and price expiration.
- `source_limits`: shared per-source minute budgets and rejection cooldown.

## Reuse and refresh

Nearby searches use the same fixed H3 viewport centre and bucketed radius for GasBuddy,
Maps whole-area searches and Waze. Maps expansion retains its H3 query centres,
fixed radius ladder and partial-coverage evidence. Personal eligibility and
ranking are applied after source acquisition, with real visitor coordinates.
A cache entry never proves coverage beyond what its original response proved.

For 15 minutes (`GASWISE_PRICING_CACHE_FRESH_SECONDS=900`) all callers, including
manual refresh, reuse the same provider result. After that, usable data is returned
immediately while one lease owner refreshes it. Other callers reuse that data.
Stale responses can be served for at most one hour from their successful query.
The next visible browser check reads a completed refresh; no extra browser polling
or unbounded whole-world background refresh is introduced. Cold requests wait up
to 20 seconds for another process's existing load instead of duplicating it.
Failures/cancellation release a lease with a short 30-second retry delay. A lease
expires after worker death. Network I/O never holds a DB transaction open.

`SmartSnapshot.source_cache` exposes each source's oldest participating query
check time and whether any participating query was stale. Original price report
and fetch timestamps are preserved. The frontend shows this shared-data status;
`collected_at` remains the time the user's snapshot was assembled.

## Retention and request budgets

A known price report expires at its original report time plus 72 hours. A report
without a source timestamp expires six hours after its original fetch time. An
unchanged old quote fetched today cannot renew its age. Expired quotes are excluded
at read and ranking time, even before physical cleanup. An hourly maintenance task
deletes expired quote rows, prunes cached price arrays, and removes unusable cache
entries. Station identity and mappings survive quote deletion. The shortest
user-requested freshness requirement still takes precedence.

Actual outgoing HTTP calls are charged before sending: GasBuddy bootstrap and
pagination; Maps discovery, details, geocoding and website route requests; Waze
search and authentication calls. Default shared minute caps are respectively 12,
60 and 20, configurable through `GASWISE_*_REQUESTS_PER_MINUTE`. These are operator
starting budgets, not provider-published safe limits. Shared budgeting currently
requires GasBuddy's HTTP transport; browser transports are rejected when enabled
with PostgreSQL because their implicit browser requests cannot be counted here.

HTTP 429 respects `Retry-After` when present. Repeated 429/401/403 and explicit
challenge responses apply an increasing shared cooldown. No request rotates
identities or bypasses source limits. Data retention follows the operator's source
permissions; this schema does not establish upstream storage rights.

## Verification

Normal tests use `uv run pytest -q` and do not create DB containers. The opt-in
`tests/storage/test_postgres.py` reads `GASWISE_TEST_DATABASE_URL` and exercises the
existing database with isolated temporary keys/IDs, deleting only its own rows.
It verifies concurrent reuse across pools, stale background refresh, reuse after
connection restart, shared rate caps/cooldowns, and price cleanup retaining station
identity. Source calls in this integration test are fixtures, not live provider
coverage proof. Never print a connection URL, password or environment dump.

The integrated personal-search, price-refresh and route-reuse design is in
[search-cache-architecture.md](search-cache-architecture.md).

## Adaptive hot-query refresh pilot

`GASWISE_HOT_PRICING_REFRESH_ENABLED=true` enables the pilot (default false).
Live mode and shared PostgreSQL are required. It reuses SmartService public query
keys and coverage, without city-wide scans or personal routes. Restart clears its
process-local demand registry; database counters and cooldowns survive restart.

The bounded registry holds 20 recent queries by default
(`GASWISE_HOT_PRICING_REFRESH_MAX_QUERIES`, 1–100). At least three foreground uses
within the last hour qualify. Uses expire individually after an hour; idle queries
are removed. Counts include browser refresh actions and are not unique user counts.
When full, new queries stay on-demand until slots expire.

The scheduler checks once per minute and considers at most one acquisition per
tick. With the default minimum interval of 900 seconds:

| Foreground uses in the last hour | Update interval |
| --- | --- |
| 0–2 | No proactive acquisition |
| 3–5 | 60 minutes |
| 6–11 | 30 minutes |
| 12 or more | 15 minutes |

`GASWISE_HOT_PRICING_REFRESH_INTERVAL_SECONDS` sets the minimum (900–3600), never
shorter than cache freshness. Normal demand pacing is capped at one hour. A
provider failure doubles the source pause, up to six hours; successful background
loads reduce the failure level one step at a time. Cached reads do not establish
provider recovery. Known shared provider cooldown also suppresses scheduled loads.

All background actual HTTP calls inherit a context marker, including pagination,
bootstrap and details. Database row locks enforce across workers:

- Existing total per-source minute caps remain unchanged.
- Background stops when total minute usage reaches half the source cap.
- Background has its own cap of 20% of the minute allowance (minimum one call).
- Background has a rolling 24-hour cap per source, default 100 HTTP calls
  (`GASWISE_HOT_PRICING_REFRESH_DAILY_REQUESTS`, 1–1000).

These hard caps apply at each outgoing request, not just at query start; a query
can stop partway through pagination. Background acquisition uses identical cache
leases and source slots, and cannot bypass freshness or rejection cooldowns.
Counters include attempts before network I/O, so network failure does not restore
spent allowance. Foreground retains the original total budget. Demand-driven
stale revalidation remains part of foreground acquisition; the extra allowance
applies to proactive scheduled work.

Authenticated `GET /v1/sources/refresh-status` reports demand registry sizes,
source usage, cooldowns, backoff and completed loads. It exposes no query keys,
coordinates, cookies or visitor identifiers, and is not exposed by the public
frontend gateway. `scripts/smoke/check_hot_pricing_refresh.py` runs inside the
backend, tests isolated database budget counters, and makes three bounded public
DTLA searches without routes, details or targeted lookups.

Enable only with appropriate source acquisition/storage permissions. Compare
actual upstream HTTP calls per search, cache hits, rejection rates, original quote
age and unique station coverage with an on-demand-only baseline before expanding.
Provider rejection-rate improvements are not assumed from implementation alone.

### Production pilot validation on 2026-10-13

Release `b149f2dc34e322c195409ed06395a5d299755835` was deployed through the successful
GitHub test/publish/deploy workflow. Both running GHCR containers were healthy and
public HTTPS and the public search gateway returned 200. The pilot is enabled
with 12 registered queries maximum, a 900-second minimum interval and 40 proactive
HTTP calls per source per rolling 24 hours.

Three repeated internal HTTP searches after the shared refresh completed returned
21 quote records with four cache hits and zero upstream calls each, taking
0.05–0.07 seconds. A public HTTPS search returned the same quote count, four cache
hits and zero upstream calls. These timings are warm-cache internal samples, not
cold search or production load-test measurements. GasBuddy supplied ten quote
records and Waze eleven; Maps acquisition succeeded but supplied no Premium quote
with details disabled. This is not complete city or pump-price verification.

Existing production PostgreSQL tests with isolated temporary source rows verified
shared background minute/daily caps and retained foreground capacity. The isolated
runtime scheduler fixture verified the inherited background request marker and
that source pressure suppresses acquisition, with zero provider HTTP calls.
`check_hot_refresh_runtime.py` reproduces that test. No natural scheduled refresh
had completed at the time of this check; long-term rejection-rate improvement is
not established. The first smoke attempt rejected differing observations; the
version-aware smoke now checks timestamp invariance within the same source-cache
version, allowing changes when a source refresh has completed.

## GasBuddy background pagination across minute windows

GasBuddy background acquisition now preserves its cursor and accumulated pages
when the local minute budget is exhausted. It waits for the remaining database
window (at most 60 seconds per sleep) and charges the next request atomically
before sending it. A single request's budget wait is bounded to three minutes.
Daily-budget exhaustion, shared cooldown, rejection and database failure stop the
acquisition immediately; no rejected HTTP request is retried. Cancellation
interrupts a wait and releases the existing cache lease. Lease heartbeats continue
while acquisition waits.

One reusable background anonymous HTTP session and one background GasBuddy source
slot keep those waits separate from foreground transport and concurrency locks.
Both lanes share the existing database total counters and rejection cooldowns;
the extra lane never grants extra upstream allowance or switches identity in
response to source refusal. The background session uses the same configured
transport/proxy and normal session expiry. Shutdown closes both sessions.

`check_gasbuddy_background_pages.py` makes one explicitly authorized live
three-page city query under the real shared background budgets, with no other
provider acquisitions, routes or station details. It prints only station/quote
counts and charged HTTP totals. Bootstrap consumes one request in addition to
pages, so a cold three-page query normally costs four background HTTP calls.

## Fixed city bases for history, independent of search traffic

Enable `GASWISE_BASE_COLLECTION_ENABLED=true` with shared PostgreSQL and live mode.
`GASWISE_BASE_COLLECTION_BASES=["la","irvine","sd"]` selects public city-centre
sampling bases for Los Angeles, Irvine and San Diego. Each base uses a fixed
10-km H3-snapped query circle, Regular/Premium (and native Waze fuel grades), and configured GasBuddy,
Maps-web and Waze providers. This samples bounded source results, not entire cities.
GasBuddy permits three pages and preserves both payment variants; Maps permits
three Premium detail requests. No routes, vehicle identities or visitor searches
are required. Premium does not establish 91 octane or a known payment basis.

Five jobs per base (GasBuddy and Maps Regular/Premium, Waze all-reported-fuels) are persisted
in `gaswise.base_collection_jobs`. New jobs are due immediately; each successful
job becomes due after 24 hours (`GASWISE_BASE_COLLECTION_INTERVAL_SECONDS`, minimum
86400). Existing schedules survive restart; startup only upserts configuration.
Removed/disabled sources/bases stop being scheduled without deleting price history.
A 15-minute owner lease and atomic claim prevent duplicate job execution across
workers; interrupted work releases its lease, or becomes reclaimable after expiry.

The worker drains initial due work at ten-second spacing after successful jobs,
then checks idle/deferred work once a minute. Provider minute/day caps, pressure
checks, cooldown and GasBuddy's bounded cross-window waits remain in force. Failed
loads retry after an hour; budget deferrals after 15 minutes. A source's due base
jobs take priority over extra demand-driven warming; they do not share the bounded
hot-query registry. The 40/day deployment allowance is shared by both collectors,
not added to it, so completion is not guaranteed under rejection or exhausted caps.

The existing shared cache saves public station/quote observations and the
90-day `quote_history` as part of acquisition. Same source reports are deduplicated;
re-observation updates last_seen, not original report time or a fabricated daily
price point. Serving cache expiry does not delete historical observations.
Fresh cached results can satisfy an initial job; stale entries must finish refreshing
before the job is marked successful. Authentication/session failures remain explicit.
`/v1/sources/refresh-status` now includes each base job's next due time, last success,
retry state and last quote/station counts. None of these require foreground traffic.

### Expanded SoCal registry

The [SoCal research and full base list](socal-base-research.md) defines 85 public
bases across eight counties. `GASWISE_BASE_COLLECTION_BASES` accepts their validated
IDs; source catalog data ships in the wheel. `GASWISE_BASE_COLLECTION_PRESET=socal`
selects all 85; `custom` uses the configured list (default original three). Older
releases ignore the preset and retain their original three-city configuration. Available sources are checked
before leasing a job so exhausted-source work keeps its place across days.
The source daily allowances are shared with hot warming and are not increased.
The 24-hour interval is a target after success, not a full-registry daily guarantee.

## Adaptive daily allowance

`GASWISE_PRICING_DAILY_RAMP_ENABLED=true` enables a persistent, per-source ramp.
The expanded production pilot starts at 80 actual background HTTP attempts per
rolling 24 hours, keeps floor 40 (`GASWISE_PRICING_DAILY_RAMP_FLOOR`) and ceiling
800 (`GASWISE_PRICING_DAILY_RAMP_MAX`). The existing
`GASWISE_HOT_PRICING_REFRESH_DAILY_REQUESTS` is the initial/static fallback allowance.
These are operator limits, not provider-published safe limits.

PostgreSQL serializes reviews under the existing source row lock. After a full
24-hour review interval, a source doubles only if at least 75% of its current
allowance was actually attempted during that review and no source rejection or
fixed-collection failure occurred. At most one step is applied per review, even
across workers or after long downtime. Idle/underused sources hold their allowance.
The path from 80 is 160, 320, 640, then 800, subject to those conditions.

HTTP 401/403/429 or explicit challenge immediately halves the current allowance,
with floor 40, starts a new observation interval and retains the existing shared
cooldown. Fixed-collection failures restart the clean observation interval without raising the allowance. Review attempt
counters are separate from rolling daily usage: increasing, decreasing or restarting
never resets spent daily requests, and earlier-window requests do not count again
as new review activity. If usage already exceeds a reduced allowance, proactive
acquisition stops until the daily usage window permits it.

Both fixed-base collection and hot warming read the effective database allowance;
each actual HTTP call enforces it atomically. Minute totals, the background 20%
minute slice, the 50% foreground reservation, foreground allowance and source
cooldowns are unchanged. The status endpoint exposes effective allowance, floor,
ceiling, review timestamp and review attempt count per source. Disabling the policy
at startup restores the configured static allowance. All workers should use the
same policy settings.

`check_daily_ramp.py` verifies concurrent review, restart reuse, immediate reduction,
and retained daily counts against isolated temporary database rows with zero
provider HTTP calls. Fixture review timestamps do not prove a natural clean day
or that higher limits improve coverage or avoid provider protection.

### Weighted city rotation

LA's five source/fuel jobs are mandatory targets at the configured collection interval
(24 hours in production). Due LA jobs precede optional cities. Optional jobs score
`10 × log10(1 + population) + 2 × overdue hours + 30 if never sampled`.
Unbounded waiting credit lets smaller cities eventually outrank larger cities;
these are scheduling weights, not measured fuel-purchase rankings.

Within each source's rolling daily budget, pending LA jobs due before the window
ends reserve conservative HTTP allowances: GasBuddy 4 per grade, Maps 1 plus
configured details, Waze 3. Each outgoing optional background request checks the
reservation under the shared source row lock, including hot-query warming.
Mandatory jobs still obey the source's daily/minute ceilings and cooldowns.
Provider failures can therefore miss the target; authenticated refresh status
exposes `mandatory_due`, `priority_score`, last success and errors for inspection.
The target covers the existing bounded city samples, not every station in LA.

### GasBuddy task pacing

`GASWISE_GASBUDDY_BACKGROUND_PACING_ENABLED` defaults to true. PostgreSQL reserves
one optional job start per `request_reserve × 86400 / effective_daily_limit`
seconds, serialized across workers and retained through restarts. At 160 daily
requests and a four-request job estimate this is 36 minutes. Due mandatory LA
jobs bypass the start interval, while all HTTP minute/day caps and cooldowns remain.
This spaces bounded jobs; it does not guarantee a precise daily station count.
Local budget/minute-wait/reservation exhaustion is retried as a named deferral,
without resetting the healthy-provider review. Actual acquisition failures and
provider rejections retain their existing review/cooldown behavior.
