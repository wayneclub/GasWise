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
