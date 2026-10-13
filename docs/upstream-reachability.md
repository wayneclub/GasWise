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

## Missing-price extraction audit

A subsequent live AWS audit around public ZIP 90015 checked the source fields
before removing unpriced cards. Google returned 20 discovered stations, 14
Regular summary quotes and no Premium quotes; five bounded detail requests also
returned no field-86 fuel tables. No Regular price was substituted for Premium.
Waze returned 20 venues with 64 positive grade-price entries, including 20
`gas_premium` entries; none of those entries had an empty or non-positive price.
A separate local GasBuddy live audit compared positive raw Premium cash/credit
reports with parsed results: five raw reports became exactly five quotes, across
three priced stations and two pages. AWS GasBuddy remains challenged, so this
local result does not establish its deployed coverage.

The UI problem was discovery inventory being displayed before any source quote
was required. Nearby cards now merge sources first, then omit stations without
a finite positive price. A real Waze/GasBuddy quote can still supply a Maps
inventory station. Unpriced inventory is retained internally for closure matching
and honest coverage diagnostics; it is not a recommendation or a displayed card.
These observations are a bounded sample, not proof that all upstream responses
always have the same shape or that every station is covered.

## Reusable transport and package investigation

The shared `providers/http/curl_client.py` transport now handles bounded async
GET/POST reads, host allowlists, standard/browser TLS profiles, and explicitly
owned in-memory guest sessions. AAA uses standard libcurl. GasBuddy's optional
`GASWISE_GASBUDDY_HTTP_CLIENT=curl` or `curl_chrome` modes reuse the same transport
with guest cookies/CSRF owned by its existing expiring session worker. The
production default remains `httpx`: the alternatives have not restored AWS
GasBuddy, and no automatic retries or challenge-script execution are introduced.

Fresh AWS evidence on 2026-10-12:

- Shared standard transport: AAA publication 2026-10-12, 90 rows, counties available.
- `curl_cffi` Chrome profile: GasBuddy HTTP 403, `cf-mitigated: challenge`, no homepage token.
- Shared Chrome transport through the actual GasBuddy session worker:
  `gasbuddy_http_bootstrap_challenge`.
- PyPI `cloudscraper`: HTTP 403 challenge, no homepage token.
- Official GitHub `VeNoMouS/cloudscraper` commit
  `9ea528a8675f1bebd49ff853d142e94988a95178`: installed in an isolated disposable
  AWS container without mounted credentials; request did not complete within a
  45-second process deadline (exit 124). No successful homepage/API proof.

Package documentation describes capabilities, not universal acceptance by a
site's private WAF policy. These results do not prove the exact deciding rule.
GasBuddy direct AWS remains unavailable. A reliable restoration requires a
source-supported access path or a rule exception from the source operator; do
not label an unverified solver/alternate region as a working fix. No Mac relay,
rotating proxy, third-party CAPTCHA account, or paid subscription was installed.

Primary project references: [curl_cffi](https://github.com/lexiforest/curl_cffi),
[cloudscraper](https://github.com/VeNoMouS/cloudscraper).

A second isolated run of the same GitHub commit identified version **3.0.0**,
allowed a 60-second process deadline with a 15-second per-request timeout,
and also ended at the process deadline (exit 124) before returning a successful
source response. The first test was not assumed to establish universal failure;
the second still provides no successful source or GraphQL proof.

## Additional bounded AWS probes

2026-10-12, same deployed container and direct AWS egress: curl_cffi Firefox,
Safari, and Chrome forced to HTTP/1.1 each returned HTTP 403 with
`cf-mitigated: challenge` and no homepage CSRF token. A normal anonymous
SearchPrices POST to the existing public GraphQL endpoint also returned a
challenge and no data. No clearance cookie, alternate proxy, or Mac relay was
used. These tests do not establish which private WAF rule makes the decision.
