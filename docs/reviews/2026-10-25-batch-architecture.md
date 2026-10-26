# Batch and acquisition architecture audit — 2026-10-25

Scope: production PostgreSQL aggregates and deployed `2216c8c`; acquisition,
shared caching, budgets, background scheduling, lifecycle and snapshot signing.
This is not a security audit or proof of exhaustive station coverage. Production
inspection was read-only. All counts are a snapshot around 16:45–16:50 PDT.

## Production batch state

| Source | Current fixed city jobs | Due | Background HTTP allowance used |
| --- | ---: | ---: | ---: |
| GasBuddy | 170; each has a historical success | 98 | 800 / 800 |
| Google Maps | 85 new all-fuel jobs; no success yet | 85 | 640 / 640 |
| Waze | 85; each has a historical success | 0 | 160 / 160 |

Google's previous 85 Regular and 85 Premium jobs are disabled, with success
history retained. New job identities do not inherit their schedules. Their
immediate backlog is a migration effect plus exhausted allowance, not evidence
of upstream rejection. No source had an active provider cooldown at inspection.
All background sources are gated by local daily allowance until their rolling
24-hour window resets. These are not midnight calendar-day windows.

DTLA daily coverage: 32 / 48 known station/fuel targets checked, 16 missing.
That is partial coverage. In the last 24 hours, GasBuddy recorded 76 successful
attempts, two source failures and 51 `coverage_missing` deferrals. Maps recorded
170 successes and two failures; Waze recorded 85 successes and four failures.
Those totals include work preceding this deployment and must not be attributed
to the new release.

Daily observations are not fresh pump-price verification. On the current LA
calendar date, Waze had 212 observation rows, 189 with source report times older
than 24 hours; GasBuddy had 3,638 rows, 2,371 older than 24 hours. All 207 Google
rows had unknown source-report time. These are observation rows, not unique
stations. The upstream may return old or undated prices despite HTTP success.

## Findings

### P1 — Background revalidation used foreground budget identity (fixed locally)

`SharedPricingCache.get` starts a detached task when returning a usable stale
result. The task inherited its foreground caller's context, and `_background`
did not set `background_acquisition`. Consequently RequestBudget admitted its
HTTP as foreground work: the global minute limit still applied, but the
background minute/daily allowance and mandatory reservation did not.

A test through `get -> _background -> RequestBudget.before -> consume` reproduced
the wrong admission arguments. The local fix explicitly sets background context
and clears mandatory privilege during revalidation, restoring both in `finally`.
A second test confirms exhausted background allowance prevents another HTTP
operation while preserving the stale result and releasing the lease. These
changes have not been published or deployed as part of this audit.

### P1 — Demand cadence overcommits the same quota used for daily coverage

All registered demand viewports remain eligible for updates every 15 minutes
for fourteen days. Registration needs one foreground request, not sustained
recent use. At inspection there were 11 GasBuddy, 38 Maps and eight Waze active
warm jobs. If each were refreshed 96 times/day, even one HTTP per job would
require 1,056 / 3,648 / 768 HTTP respectively, before city sampling, hotspots,
pagination, details or retries. Actual warming is throttled and does not reach
that nominal cadence; the consequence is overdue work.

Only mandatory LA/hotspot work has reserved allowance; other cities and demand
warming compete. The cycle reserve of 2,125 HTTP is a separate configuration
limit, not a proof that the deployed per-source daily allowances can fund it.
GasBuddy alone reserves 1,530 HTTP for a maximum-pagination city pass against
an 800-HTTP current allowance. At the observed 470 HTTP / 76 successful attempts,
a simple 170-job estimate is about 1,051 HTTP before repairs or warming; this is
an estimate from a mixed workload, not a guaranteed city-pass cost.

Recommended design: one per-source admission policy with explicit city,
hotspot and demand shares; derive warming frequency from remaining allowance,
recent demand and measured request cost. Keep old demand registrations for
reuse, but do not promise 15-minute polling of every retained viewport. Publish
forecast completion time and overdue age, not just success rate. Do not raise
upstream limits merely to satisfy an infeasible schedule.

### P2 — One city scheduler blocks independent sources behind slow GasBuddy work

`BaseCollection.run` awaits one complete `step` before claiming another job.
GasBuddy HTTP budget waits occur inside that step. Successful GasBuddy attempts
averaged 147.51 seconds in the inspected day, with a maximum of 360.82 seconds;
Maps/Waze successes averaged 1.47 / 1.38 seconds. These include budgeting and
network work, not just provider response time. With mixed due work, an idle
Maps/Waze slot cannot progress through this scheduler until the current job
finishes. This does not explain the current all-quota-exhausted state, but it
reduces recovery throughput once allowance is available.

Recommended design: one bounded worker per source, continuing to use shared
PostgreSQL leases and global HTTP admission. Persist a future due/admission time
rather than sleeping inside a worker for minute-budget waits. Coordinate hotspot
registration separately. Increasing generic concurrency alone would not solve
the quota deficit and could increase source pressure.

### P2 — Deployment migration resets scheduling when job identity changes

The new Maps `all` identity inserts 85 new jobs; initialization disables the
previous identities without copying their last-success/next-due state. Existing
quote history is safe, but this produces a due-work spike and temporarily makes
current-job completion look like zero coverage. Future transformations should
have an explicit transactional identity migration, conservatively inheriting
compatible coverage and due times, with provenance retained. Report migration
backlog separately from source failure.

### P2 — Monitoring does not distinguish retrieval, freshness and scheduler health

The container health endpoint checks app response only. A successful task may
return old reports, undated summaries or zero usable prices. Demand refresh is
not written into the fixed-job attempt journal, so that journal cannot reconcile
all background HTTP usage. Operators currently need separate tables to explain
allowance exhaustion. The inspected database has modest table sizes (about 86k
history rows); there is no evidence here that database scale is the main issue.

Recommended metrics: last source HTTP success, last batch progress, due-job age,
daily target coverage, dated/undated/expired price counts, allowance consumption
by acquisition purpose, HTTP/usable-price yield and deferred reason. Health
should show worker progress without treating intentional quota deferral as a
crash. Retain source timestamps and unknown-payment semantics.

### P2 — Snapshot signing is tied to process lifetime

Bootstrap generates a random signing key per process. A snapshot from process A
cannot be reranked by process B or after a restart. The current Docker command
runs a single Uvicorn process, so this is a restart/scale limitation rather than
proof of a current multi-worker incident. Before adding workers or replicas,
use a private persistent signing key with rotation/versioning. Progressive
search jobs and in-memory route caches also need an explicit process-affinity
or shared-state strategy. Do not scale the process count as a quick performance
fix.

## Recommended implementation order

1. Publish the tested background-admission correction as a separate change.
2. Budget city coverage, hotspot repair and demand together; expose the resulting
   feasible cadence and target shortfalls.
3. Isolate source workers and add progress/freshness/purpose metrics.
4. Add transactional job migration and stable snapshot signing before scaling.

Current useful safeguards should remain: cross-process query leases; atomic
cache save/observation writes; per-request global source budgets and rejection
cooldowns; unchanged source timestamps; no mid-query exit switching; original
quote history and client-side private vehicle/profile data.

## 2026-10-26 implementation follow-up (local, not yet deployed)

- Stale revalidation now sets background context and clears mandatory privilege.
  A failed cache save after lease loss is explicitly an error, not a successful
  fresh read.
- A single domain policy caps demand warming plus stale revalidation at 20% of
  the source's rolling daily allowance. PostgreSQL enforces that cap atomically
  during every outgoing admission; city/hotspot work uses the remaining shared
  total, and all work retains the existing minute limits and provider cooldowns.
  City/hotspot work can use unused optional capacity; 20% is a ceiling, not a
  guaranteed demand allocation. Historical usage before this migration cannot
  be split retrospectively by purpose.
- Warming costs include bounded pagination, detail requests or Waze session
  setup reserve. Warming intervals grow with the total recent query cost and
  optional allowance. Retention stays fourteen days, but only demand from the
  last 24 hours is actively warmed. Renewed foreground demand reactivates it.
  Every source has its own bounded warming loop; local quota deferral is not
  classified as a provider failure. Shared SQL caps remain authoritative across
  restarts/processes; process-local pacing is an extra smoothing mechanism.
- City collection uses one worker per source. GasBuddy may still wait within
  its own worker to finish bounded pagination, but no longer holds up Maps or
  Waze collection. Full resumable pagination would be a separate design change.
- Compatible legacy Maps schedules migrate transactionally with explicit parent
  identifiers. Different viewports/query limits, running jobs and jobs with
  existing results/failures do not inherit the old schedule.
- Refresh status adds per-source purpose usage, warming costs and planned
  intervals, due-job age, worker loop progress, dated/old/undated observations,
  and conservative city-cycle capacity. Forecasts are based on reserved request
  costs and exclude hotspot/retry costs; they are not promises of complete daily
  coverage or verified fresh prices.
- Snapshot signing uses a persistent private 32-byte singleton key in
  `gaswise.runtime_secrets`. Independent pools share it atomically. Do not expose
  that table through status/export tools. A first transition invalidates snapshots
  signed by the old process-random key. Rotation is not automatic; deleting or
  replacing the singleton invalidates existing signatures. Progressive job state
  still needs process affinity before a multi-worker deployment.

The isolated PostgreSQL smoke script is
`scripts/smoke/check_background_architecture.py`; it requires a dedicated
`gaswise_arch_...` database and resets only that test database's `gaswise` schema.
It checks purpose caps and daily reset, shared signing key, compatible/incompatible
job migration, warming cost/leases/dormancy and freshness metrics. No provider
requests are made by it. The production pricing database was not modified by
these integration checks.
