# Persistent inventory and bounded cell discovery

Station inventory is distinct from price freshness. The existing `stations`
table now remembers unpriced Maps cards and station identities from original
provider payloads before quote-age pruning. Cache hits do not become new station
observations. Existing blobs seed inventory with their original fetch times;
older metadata does not overwrite a newer observation. Known permanent closures
are excluded from the active discovery catalog without deleting their history.

Maps discovery uses a stable H3 grid and radius ladder. Its existing query budget
remains authoritative. Known stations omitted from a response keep nearby cells
eligible even if geometric sampling considered the cell covered. Detail-free
cards share a canonical Regular / 20-result query across requested grades;
responses retain all reported grades and project the requested grade afterward.
Station detail enrichment remains separately bounded and grade-aware. A region's
cell geometry is held in bounded process memory for five minutes, so a growing
catalog does not turn repeated hot searches into a new batch of cell reads.
It then replans from the latest known gaps; individual source data timestamps
and source cache expiry remain independent.

The snapshot reports newly observed IDs, historical known IDs recovered/missing
and duplicate returns separately. Missing known Maps stations can be retained
as `discovery_state=known` with an original `last_seen_at`, no price and no current
opening claim. They do not provide live crosswalk/closure evidence. UI fallback
cards explicitly mark them as not rediscovered. Geometric area coverage is only
a survey estimate; relevance ranking cannot establish exhaustive coverage.

Waze starts with one all-fuel area query. Known missing Waze identities are grouped
into fixed coarse cells; at most three additional cell queries are admitted
within a maximum four-query budget, also bounded by the caller's discovery
budget. No station-by-station lookup is used. Responses are deduplicated by
station/grade/payment and filtered to the original search boundary. Expansion
stops on zero marginal station yield or a source error, preserving prior results.
The same all-fuel cell keys are reused across grades and users.

`discovery_cells` records actual capped survey responses. Capped cells generate
bounded, spaced child cells in `discovery_patrol`. One low-frequency patrol worker
runs when fixed-base collection is enabled, uses the shared Maps cache and spends
only the existing optional background allowance (shared with demand and stale
revalidation). It never increases source limits. Completed cells are due after
24 hours; failure/shutdown releases the lease and retries after fifteen minutes.
Inactive work expires after ninety days. City sampling and foreground query
budgets remain unchanged. Queue progress is exposed in refresh status.

The reproducible public-region comparison is
`scripts/diagnostics/discovery_comparison.py`. It uses DTLA and Bakersfield, eight
Maps discovery queries, no detail or address lookups, one GasBuddy page and no
routes. It records observed versus retained inventory IDs, Waze query count,
cache hits, duplicate yields and wall time. Before/after wall times are not pure
cold-cache comparisons because shared caches remain enabled and source ranking
can change. Historical retention is reported separately, never counted as newly
fetched coverage. Neither provider offers a verified exhaustive ground truth.
