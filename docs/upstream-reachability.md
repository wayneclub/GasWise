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

## Controlled Docker comparison and direct AAA recovery

Subsequent probes used the **same immutable multiarch image**
`sha-11d1a608fa45455ed57f9a6b2ddeab825cdcb25f`, Python 3.12.15,
OpenSSL 3.0.22 and HTTPX 0.28.1 on both the Mac's Linux Docker engine and AWS.
Fresh sessions, identical URLs/headers, no environment proxy, HTTP/1.1 and HTTP/2:

| Request | Local Linux container (LAX edge) | AWS container (NRT edge) |
| --- | --- | --- |
| GasBuddy HTTPX, HTTP/1.1 or HTTP/2 | 200, expected homepage token marker | 403, challenge |
| AAA HTTPX, HTTP/1.1 or HTTP/2 | 403, challenge | 403, challenge |
| AAA standard libcurl on AWS | — | **200, dated public tables** |

This separates two different problems. GasBuddy shows an environment/network
path-dependent decision with equivalent client binaries. IP/ASN reputation,
geography and edge policy are candidates, not proven private-rule details.
AAA's result changes with the HTTP/TLS implementation on the **same AWS server**;
it is therefore not a blanket AWS IP rejection. HTTP protocol selection alone
did not resolve either failure.

AAA now uses a fresh **standard libcurl** session (no browser impersonation,
clearance cookies, challenge execution or external proxy). Reads are restricted
to `gasprices.aaa.com`, bounded to 4 MB, and retain publication date and official
source URL. A full adapter call **inside AWS** returned publication 2026-10-12,
90 state/metro/county rows, county status available, and Los Angeles–Long Beach
Premium 6.7405. This is live retrieval proof, not a mocked contract.

The proposed Mac relay was explicitly cancelled by the user. Its two local
LaunchAgents and reverse SSH socket were stopped/removed, and its uncommitted
application integration was reverted. Production never depended on that relay.
GasBuddy direct AWS reachability remains unresolved; do not infer that AAA's
transport fix also restores GasBuddy or manufacture missing quotes.
