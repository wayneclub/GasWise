# Price observations

The existing PostgreSQL `gaswise.quote_history` table records public quote
observations independently of `gaswise.quotes`, the expiring serving cache.
It is created idempotently at backend startup. No additional database/container
is needed. Raw history supplies station-specific payment estimates, while the 72-hour price expiry
still applies to the serving cache.

Keep exact source price, fuel/payment conditions, source report timestamp,
first/last observed timestamps, source station ID and canonical ID when available.
Only allowlisted public station attributes are retained; no login/session data.
The same price/report/conditions is deduplicated across fetches. Price, conditions
or report-time changes produce new observations; unknown report times use daily
buckets. These are observations, not proof of the exact moment a pump changed.

History is deleted after 90 days without observations; estimation uses only 30 days. No historic observations can be
reconstructed from overwritten cache values. Existing records are not backdated
or labeled as newly reported. Collection begins when this backend is deployed.

Offline evidence lives in `artifacts/price-analysis/`. A 100-quote sample is not
100 matched station pairs. Same-station, same-grade, membership, report age and
price precision must be validated before using it to classify payment terms.

## Payment inference

Raw payment labels are never rewritten. A same-station, same-grade/conditions
price match within 30 minutes with less than $0.01 difference is medium-confidence evidence (not pump verification).
Both cash and credit matching is classified as same_price. History estimates
require three distinct report days, cash/card pairs within 30 minutes from the
same provider and station, at least 48 hours between earliest/latest pairs, spread variation at most $0.03, and a pair in the last
seven days. The median spread estimates credit comparison price only when current
unknown pricing matches a cash report. No global surcharge or numeric probability
is invented. Raw price and estimated comparison price/range remain separate.
Snapshots retain bounded public raw history so reranking needs no database/provider
calls. Estimates never become historical evidence. Missing history is nonfatal.

Known same-day payment quotes precede unknown quotes; older explicit quotes do not
perpetually suppress fresh unknown evidence. Maps/Waze share one evidence family.
Frontend corroboration requires backend corroborated quality. Inference confidence
expresses the payment evidence rule, not accuracy of the current pump price.

New unknown-payment reports conflicting with an older selected card quote widen
comparison bounds and produce a price-change warning rather than silently
relabelling unknown prices. Bounds are evidence/sensitivity ranges, not statistical
confidence intervals and do not guarantee the actual pump price lies inside them.
Payment labels explicitly reported by sources have medium evidence strength, not
a calibrated accuracy probability. Correlated-feed conflicts remain visible.
History is partitioned by station/grade/payment/conditions, malformed records are
skipped, and rejected acquisition evidence cannot classify current payment.

Run `scripts/smoke/check_payment_history.py` inside the deployed backend to verify
actual PostgreSQL history read/write, estimate, repeat ranking and missing-history
fallback. Its validation rows are rolled back and it makes zero upstream calls.

## User interface and read API

Open a station's details, then expand **Price history** below its current quote.
The 7/30/90-day controls read existing observations only, with no upstream calls.
The selected fuel grade stays fixed to the station detail quote. Source, source
station ID, payment basis and purchase condition define separate series. Unknown
payment is labelled explicitly; estimated comparison prices never enter the chart.
Period low/high and first-to-last change describe only the selected recorded
series. Dashed connections are visual guides, not verified gap prices. One record
has no trend; missing observations and unavailable storage have distinct states.
The table uses local report time, or explicitly labelled collection time when the
report time is unknown. History starts with collection; no backfilling is implied.

Authenticated `POST /v1/prices/history` accepts `canonical_id` (optional), `source`,
`station_id`, `fuel_type`, and `days` (7, 30 or 90). The production gateway exposes
this read endpoint. Results contain at most 1,000 latest observations; `truncated`
is explicit and limits all displayed statistics. No configured history store
returns 503, while an empty matching period returns an empty list. Queries match a
verified canonical identity or the exact source/station pair, never station names.

## Daily checks and popular-area repair

New actual fetches also write `quote_daily`, keyed by source-report identity and
America/Los_Angeles fetch day. Repeated fetches of one report on the same day merge;
a real fetch on a later day adds a check without changing the source's report time.
No missing day is interpolated or reconstructed from a first/last-seen range.
The history endpoint labels these `daily_check` and uses collection time on the
chart; the original report time remains visible. Existing report-only history is
retained and labelled `report`. Payment inference continues using `quote_history`
so repeated checks cannot manufacture independent source report days.

The initial popular area is a fixed 3 km circle around DTLA (34.0407, -118.266),
including the 90015 example and Speedway Express 10929. It covers known GasBuddy
stations seen within 90 days, excluding permanently closed stations; it is not
an exhaustive ZIP polygon. Regular and premium are checked separately. Recent
30-day payment/purchase-condition series must each have an actual fetch today;
a cash-only result cannot complete a known cash/credit station's grade.

Missing station/grade targets get durable mandatory jobs using one-page searches
centred on the station (1.5 km). Any nearby acquisition can satisfy a target, so
one search can remove several pending jobs. Every minute the collector recomputes
missing work. Each target gets at most three completed price/missing-result/source
failure attempts per Los Angeles calendar day, with hourly missing-result retries.
Budget deferrals and shutdown do not consume that allowance. Leases coordinate
workers, and missing target prices are deferred rather than marked successful.
All requests retain shared source budgets, cooldowns and foreground reservations.
The dynamic queue fits the unused cycle request reserve; excess targets rotate
in as completed jobs leave the queue. It does not increase the configured caps.

`base_collection.hotspot_daily_coverage` on the existing source status endpoint
reports known station/grade targets, completed checks and missing targets. Partial
coverage remains explicit even after the retry limit or source budget is exhausted.
Daily fetching cannot guarantee a new source report or a price for every grade.
Other popular areas require an explicit area policy; city-wide rotation remains
unchanged outside the initial DTLA coverage area.

Run `scripts/smoke/check_hotspot_daily.py` with backend dependencies and the private
runtime database configuration. It creates a uniquely named isolated schema,
checks real PostgreSQL daily identity, legacy/canonical reads, LA day boundaries,
concurrent claims, ownership, repairs, payment separation and cooldowns, and removes
its schema in `finally`. It sends no provider requests or notifications and never
writes production pricing tables.
