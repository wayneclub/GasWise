# Local / AWS upstream reachability

Fresh anonymous HTTP/2 probes on 2026-10-12:

| Source | Local | AWS Lightsail Tokyo |
| --- | --- | --- |
| GasBuddy, explicit GasWise identification | 200, expected CSRF marker | 403, Cloudflare challenge |
| AAA, explicit GasWise identification | 200, publication marker | 403, Cloudflare challenge |
| AAA, default client identification | 403 | 403, Cloudflare challenge |

Both AWS responses contain `cf-mitigated: challenge` and title `Just a moment...`.
This proves a verification page replaced the resource, but does not identify
Cloudflare's private rule, or isolate IP reputation versus client attributes.
Maps and Waze work on AWS; general outbound connectivity is functioning.
GasWise's inbound CSP cannot change another website's outbound challenge.

AAA now sends explicit GasWise identification and reports challenge separately
from ordinary upstream failures. A live local adapter call returned publication
2026-10-12, 90 regional rows, and available counties. This is local evidence,
not AWS retrieval proof.

Run `uv run python ../scripts/diagnostics/source_reachability.py` from backend,
or pipe the same script into the deployed container's Python over SSH. Only safe
response metadata is logged; never print cookies, tokens, or private environment.

Recovery needs a source-approved server integration or an explicitly configured
private collector on an owned machine that can access the public data. A local
collector requires that machine online. Retain original publication/report and
fetch times, expire stale prices, coalesce calls, and report collector outages.
Neither recovery path is installed by this diagnostic change.

[Cloudflare challenge detection](https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/)
