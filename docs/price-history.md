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
