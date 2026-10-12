# Waze integration research

Researched 2026-10-09. No Waze account access, mobile station-price validation, partner application, or provider implementation performed.

## Live investigation on 2026-10-09

Playwright follow-up (user explicitly requested browser fallback): stock locally installed Chrome in a fresh anonymous context, no stealth/fingerprint modification, no imported profile/cookies. Headless editor navigation returned 200; practice UI readiness timed out, and the context's ordinary HTTP fuel request returned 403. A separate headful probe to the English editor returned 502 before any fuel read. These results do not establish that login is necessary, that Selenium would behave differently, or that browser automation cannot ever read fuel prices. The in-app browser had already demonstrated anonymous practice-mode search success. A reproducible diagnostic is `uv run python ../scripts/diagnostics/waze/check_waze_browser.py --headful` from `backend`; it is not registered as a price provider. Ruff passed. Neither browser probe retrieved a fuel quote. Community script source last commit at inspection was 2026-03-01, so the lead is not merely an abandoned 2018 example; nevertheless its current fuel endpoint remains unverified in this environment.

Pure HTTP/2 follow-up using the same approach as `GasBuddyHTTPSession`: one fresh httpx client, ordinary landing requests, shared in-memory cookie jar, and normal editor referer. Both Waze homepage and editor returned 200 over HTTP/2, no CSRF marker and no cookies at that point. A venue fuel request with the client-declared `origin=editor` returned 403. The editor source's normal `/Descartes/app/Session?language=en` bootstrap endpoint returned 403 JSON and set two cookies; bootstrap rejection was not treated as authenticated access. Unlike GasBuddy, this tested flow did not provide a successful anonymous session/API request. No browser-cookie import, challenge solver or token fabrication was used. Reproduce from `backend` with `uv run python ../scripts/diagnostics/waze/check_waze_fuel.py --http-session`.

Follow-up: a fresh normal browser request to the US `SearchServer/mozi` fuel URL also returned 403. The editor subsequently loaded successfully at `/editor`; entering its ordinary practice mode enabled location search without signing in. Its actual UI search returned HTTP 200 from `/Descartes/grpc/com.waze.mapeditor.web.api.MapEditorWebServer/searchLocations` (gRPC-Web encoded response), rather than SearchServer. The current editor client still contains the US SearchServer configuration, but no fuel-price rendering fields were found in the inspected application bundle. Successful location search is not successful fuel retrieval. The prior editor 502 was transient and is no longer the current blocker. Signed-in access has not been tested and is not known to fix the fuel endpoint.

The public Live Map successfully found 76 at 4600 Melrose Ave, Los Angeles. Browser network inspection returned HTTP 200 for `/live-map/api/venues/158400853.1584008528.5847665?locale=zh-TW`. Its JSON included name, address, coordinates, phone, hours, images and services, including `credit_cards`, but no fuel prices. Accepting credit cards is not evidence of a credit-price quote. Direct unauthenticated HTTP requests to the venue and autocomplete endpoints returned 403 in this environment.

Read, but did not install or execute, the source of the community WME BackEnd Data script:
https://github.com/TheCre8r/WME-BackEnd-Data/blob/master/WME-BED.user.js

It constructs a SearchServer request with `format=PROTO_JSON_FULL` and `venue_id=venues.<id>` and reads `venue.product` entries containing `gas.*`, `price`, and `last_updated`. A WazeWrap source example supplies the US path `/SearchServer/mozi`:
https://greasyfork.org/en/scripts/471457-wazewrap-testing/code

A direct read-only request for the verified 76 venue to that endpoint returned HTTP 403, not fuel data. The editor page also failed to load (browser 502). No price, freshness, cash/credit or numeric-octane acceptance has been verified. These community scripts establish an implementation lead, not a supported API or current access entitlement.

Reproduction: `python3 scripts/diagnostics/waze/check_waze_fuel.py`. This standalone diagnostic uses no credentials, cookies, challenge handling or retries, and is not connected to the production source registry. Source rejection exits nonzero and reports `prices_verified=false`. A future permitted session or partner integration would still require current response validation before adding a price provider.

## Decision

Use Waze as an optional navigation destination. Do not implement a Waze price provider from the reviewed public documentation: no supported public fuel-price retrieval API, authentication flow, price schema or redistribution contract was found. This does not rule out private partnerships.

## Price source and freshness

Waze supports user edits to fuel types and prices:
https://support.google.com/waze/answer/13739802?hl=en

On 2026-05-17, a Waze communities-team announcement described a gradual rollout of a new US OPIS fuel-price feed, the same feed used by Google Maps:
https://www.waze.com/discuss/t/announcement-new-us-gas-prices-feed-rolling-out/404520

The announcement confirms the rollout plan, not its completion or current coverage for a particular Los Angeles station. Do not treat Waze as wholly crowdsourced, independent of OPIS, or guaranteed real-time. No fuel-price update SLA was found in these sources. The reviewed sources do not establish reliable cash/credit separation or a numeric US 91/93 octane contract. No current mobile-app quote was verified.

## Available official interfaces

Deep Links open Waze for search/navigation; they do not return station prices:
https://developers.google.com/waze/deeplinks/

Suggested future navigation link, with coordinates taken from the selected verified station:

```text
https://www.waze.com/ul?ll=<latitude>%2C<longitude>&navigate=yes&utm_source=gaswise
```

The Waze partner Data Feed is XML/JSON traffic data refreshed every two minutes. Its documented content includes incidents and traffic jams, not fuel prices. The two-minute interval is not a gas-price update guarantee:
https://support.google.com/waze/partners/answer/10618035?hl=en

Product partner Transport SDK provides app switching and ETA/route information; its reviewed description does not provide a fuel-price export contract:
https://www.waze.com/product-partners

## GasWise implications

### Independent HTTP verification (2026-10-09 evening)

Normal HTTPS observation succeeded after temporarily adding the local test CA
to this Android 33 emulator's system trust store. A user CA alone was rejected.
No App patch, disabled TLS verification or pinning hook was needed. The earlier
TLS failure therefore did not establish certificate pinning.

The actual US App fuel search is POST
`https://rt-xlb-am.waze.com/rtserver/distrib/command`, not the editor mozi URL.
The request body contains `ProtoBase64,<base64 protobuf>` lines; response is
`application/x-protobuf`. The command envelope field is 1001, SearchRequest
2741 and SearchResponse 2742. SearchRequest supports coordinate, radius,
category `gas_station`, page size and venue location/ID. Field definitions were
verified against serialized Protobuf descriptors included in the supplied APK.

With the App stopped, HTTP returned 20 Melrose-area stations with prices;
changing coordinates returned five downtown stations. A specific venue-ID
query returned the selected 76 station and five fuel prices. Cookies and
sequence-number were not necessary for these search calls. A valid authorized
UID was necessary: absence produced "UID expected" and an old session produced
"Client should relogin". Do not infer permanent validity from a successful call.

`scripts/diagnostics/waze/query_waze_http.py` uses only Python's standard library, with no ADB,
browser, proxy or emulator dependency for HTTP queries. It emits station IDs,
addresses, ZIP codes, coordinates, currency, per-fuel prices and per-fuel UTC
update timestamps. Payment type and numeric octane stay unknown. Results are
saved under `artifacts/waze/http-*.json`.

The owner's authorized UID and captured normal login request are private files
under `~/.config/gaswise/`, permission 0600. The login request contains credentials;
do not commit, share, print or include these files in diagnostic bundles.
`--login` performs one normal POST to `/rtserver/distrib/login`, parses
LoginResponse 2745 and builds UID from the returned session ID and secret key.
The captured request has logout_other_devices=false. The initial direct login
attempt returned INTERNAL_ISSUES / RATE_LIMIT_FAILURE; this is distinguished
from HTTP success and does not trigger automatic retries.

After a backoff exceeding two minutes, one normal login using the observed
functional login headers succeeded. The HTTP client constructed and saved a
new UID, then queried five Melrose stations successfully. After stopping Waze,
removing the temporary system CA mount, restoring non-root ADB and proxy :0,
and stopping mitmproxy, another direct HTTP query returned five downtown
stations and 15 fuel-price records. `artifacts/waze/http-login-query.json` and
`artifacts/waze/http-final-no-app.json` record these successful results.
This verifies both normal HTTP login and HTTP fuel search without App runtime.
It does not guarantee credentials never expire or that this undocumented
protocol will remain compatible. Reopening the App may replace the session;
perform one HTTP login again if Waze requests relogin. Rate-limit failures stop
the tool and should be respected, not continuously retried.

### Session and Google-account clarification

### Web-login investigation

### Credential rotation investigation (after backend integration)

Further static examination of the supplied APK found a distinct modern auth
protocol (`com.waze.auth.GetTokenRequest`) with refresh_token (1),
password_credential (2) and client_info (3), plus GetTokenResponse token (1)
and token_expire_time (2). The Android UserCredentials message also has a
refresh_token alternative. This is protocol presence, not runtime proof.
Native code references Realtime_RequestAndStoreLoginToken and LoginToken.

A fresh normal HTTP password-credential login succeeded without opening the
App. Its complete response contained LoginResponse, configuration commands
and another small response; it did not contain an identified modern
GetTokenResponse or a confirmed new refresh credential. The newly issued
authorized UID was saved privately to keep the existing client working.

The older linqmap.proto.rt.GetTokenRequest was mapped from the embedded wire
descriptor as command 2146 (response 2145). One authorized HTTP request to
the already-verified command endpoint returned an explicit routing error:
neither server_type nor PROTO_COMMAND_IPC_SERVER_TYPE nor
PROTO_COMMAND_IPC_PKG_SERVER_TYPE is defined for that request. This is not a
successful token renewal and does not establish the correct modern auth URL.
No token endpoint variants, forged credentials, revoked-token workarounds or
Google MFA bypass were attempted.

The existing emulator's configuration schema and filtered public network
metadata were inspected without launching Waze; no usable modern token URL
was found. ADB was restored to non-root. No refresh implementation has been
registered in the production adapter based solely on these descriptors.
Current verified behavior remains HTTP UID renewal using a valid saved
credential. Replacement of an expired or revoked credential is unverified.

Official Waze help documents Google sign-in on the desktop Live Map:
https://support.google.com/waze/answer/9839190?co=GENIE.Platform%3DDesktop&hl=en

The current official signin bundles show Google Identity Services
`oauth2.initTokenClient` requesting `profile email`, followed by POST
`/_user/api/session/create_by_community` with `{access_token, community:"google"}`
and the normal X-CSRF-Token from the site's `_csrf_token` cookie. The frontend
uses the reply's user_id and is_connected_to_google for web login. This alone
does not demonstrate a realtime fuel API UID exchange. The access-token page
observed in the bundle is specifically used for `user.email.update`; it must
not be assumed to issue unrestricted realtime login credentials.

The signin page was opened for the user's normal Google login. Authenticated
web-to-realtime exchange remains to be validated against the resulting
authorized web session, rather than inferred from cookie names or HTTP 200.

Live browser verification showed the account name, email and logout option on
Live Map after the normal web Google-login flow. The web session cookie is
`_web_session`, HttpOnly, restricted to `www.waze.com`, with an observed browser
expiry of 2026-11-09 12:12:44 UTC. This is cookie expiry, not a guarantee of
server-side validity or the lifetime of Google/Waze native credentials. No
cookie value was printed or saved in this document. Its host restriction means
it is not automatically sent to `rt-xlb-am.waze.com` by normal cookie rules.

An authenticated-cookie fetch of the already-known SearchServer/mozi venue
endpoint returned 403 and no JSON. A direct-navigation users/info diagnostic
also returned 403, unlike the Live Map's observed in-page 200 requests, so it
cannot establish the content of the logged-in profile response. No confirmed
web-cookie-to-native-UID exchange was found. Web Google sign-in is supported;
using that sign-in to renew the native fuel API authentication remains unproven.

A follow-up on 2026-10-10 02:10 UTC verified both the saved-session query and
another independent HTTP login followed by query (one station, five prices
each). Inspection without exposing credential values confirmed the captured
LoginRequest uses password_credential with a non-email username and a password
value, not token_credential or a Google OAuth bearer token. These are sensitive
Waze protocol credentials; their account linkage and lifetime are unverified.
The user reports Google-account sign-in in the App. Do not claim the captured
internal credential is a Google password, a Google refresh token, or proven
bound to that Google account solely from its structure.

UID contains session ID and secret key, with no explicit expiration field in
the observed message. Absence of an expiry field does not imply no expiry;
Waze can expire or revoke it server-side. Pure HTTP is verified but remains
authenticated. HTTP relogin currently succeeds with the saved credential; if
that credential becomes invalid, automatic Google-account reauthentication
has not been implemented or verified. Long-term unattended operation is not
established by these short-term checks.

Commands from the workspace root:

```sh
python3 scripts/diagnostics/waze/query_waze_http.py --lat 34.0833736 --lon -118.3008564
python3 scripts/diagnostics/waze/query_waze_http.py --lat 34.0522 --lon -118.2437 --limit 5
python3 scripts/diagnostics/waze/query_waze_http.py --lat 34.0833736 --lon -118.3008564 --venue-id venues.158400853.1584008528.5847665 --limit 1
python3 scripts/diagnostics/waze/query_waze_http.py --login --lat 34.0833736 --lon -118.3008564
```

This is an undocumented protocol and has not been registered as a production
GasWise provider. Avoid bulk polling until session lifecycle and use rights are
resolved; the prototype intentionally caps each query at 20 stations.

### Android runtime verification (2026-10-09)

Follow-up HTTP independence experiment: ordinary HTTP to the previously known
SearchServer/mozi venue endpoint still returned 403. The HTTP/2 editor bootstrap
returned home 200 followed by editor 502 on this run. A temporary standard proxy
with TLS passthrough did not yield a usable fuel request; the first startup
also showed an Android not-responding dialog. This is inconclusive about TLS
pinning. The emulator proxy was restored to :0 and the proxy processes stopped.
No certificate validation bypass or account-token extraction was performed.
Independent HTTP fuel access remains unverified.

Installed the user-supplied Waze 5.24.90.901 APKM with ADB install-multiple on
the Android 33 ARM64 emulator. After the user completed onboarding, Search >
Gas returned stations near the emulator's Los Angeles location. Station detail
for 76, 4600 Melrose Ave, displayed E85 2.290, Regular 5.899, Midgrade 6.299,
Premium 6.599 and Diesel 8.890 dollars. The update label was "Updated yesterday
by RedBoogs". These are observed screen values, not independently verified pump
prices. No payment-price distinction or numeric premium octane was displayed.

Android UIAutomator exposes the fuel labels, prices, address and update label
as text, including the last partially clipped fuel card. Thus screenshot OCR
is unnecessary for this tested screen. `scripts/diagnostics/waze/read_waze_android.py` reads the
currently open station detail and emits JSON; it does not navigate, query an
HTTP API, or provide an unattended station crawler. Raw XML, screenshot and
parsed results are saved in `artifacts/waze/76-melrose-detail.*`.

This proves an ADB accessibility extraction route. It does not resolve the
previous HTTP 403 results, establish a public API, or guarantee scalability.

Keep AAA regional averages and station quotes separate. Add Waze navigation only when requested. If fuel-price access is important, ask Waze product partnerships whether a commercial consumer-app fuel export is available and obtain the schema, pricing, station coverage, timestamps, payment conditions, numeric octane and display/cache rights before implementation. OPIS retail data licensing is a more directly documented route to investigate for the upstream feed.

### Web-to-Android credential bridge follow-up (2026-10-09)

Further inspection of the installed APK's embedded protobuf descriptors found
`linqmap.proto.socialmedia.GetUserFromTokenRequest`: community (1), token (2),
client_name (3), force (4), access_token_type (5), device_type (9).
Its response contains UserInfo and status; UserInfo includes access_token (27).
This is a candidate social-login bridge, not a verified credential exchange:
no callable route or successful response was established. It does not itself
return LoginSuccess's server_session_id/secret_key. No guessed token endpoint
or fabricated credential was submitted.

The official web sign-in bundle's Google handler passes a Google access token
to session/create_by_community, then consumes reply.user_id and
reply.is_connected_to_google. That handler does not extract native credentials.
A fresh same-origin browser inspection confirmed _web_session is HttpOnly and
scoped to www.waze.com. The official /signin/access-token page without a scope
rendered “Something went wrong”; the inspected source's known scope remains
user.email.update, not realtime gas-price access. A read of the observed web
session/login endpoint returned HTTP 200 without a JSON credential payload.
An attempted normal Google sign-in click in the diagnostic tab produced no
observed create_by_community exchange, so it provided no fresh Google token
for a runtime bridge test.

Result: web cookies, Google OAuth tokens, Waze auth tokens and realtime UID
remain distinct credential types. Web-only acquisition of a credential accepted
by the Android login API is still unverified; the existing provider must retain
its native-credential requirement rather than advertise web renewal support.


### Observed Google web login exchange (2026-10-09, continued test)

With Network events explicitly enabled, a normal Google button sign-in
returned to Live Map. Its request to
`/_user/api/session/create_by_community` contained a valid Google access_token
and community=google, and returned HTTP 201. A normal same-origin replay with
the observed token and CSRF header returned reply fields login, message,
user_id, has_verified_email, is_connected_to_google. login was a boolean,
not a nested native credential object. No token/password/secret/session
credential fields were returned. Token values were not printed or saved in
the repository. This supersedes the earlier unobserved-click limitation.

Inspection of 120 embedded client protocol descriptors mapped
AuthenticationRequest to Container.Element field 2007. GetUserFromTokenRequest
had no Container mapping or declared protobuf service, so its presence does
not establish a realtime command endpoint.

A planned direct test of the observed Google token against native token login
was not sent: the browser rejected navigation to rt-xlb-am.waze.com with
ERR_BLOCKED_BY_CLIENT. This is a test-environment limitation, not an upstream
INVALID_TOKEN response. Google-token acceptance by the Android login API
remains untested. The HTTP provider's existing native credential configuration
was not replaced. Sanitized evidence: artifacts/waze/web-native-bridge-test.json.


### Owner-configured password resolves Google-bootstrap dependency (2026-10-10)

Normal App login using the account's existing username and newly configured
Waze password succeeded; captured LoginRequest.password_credential matched
those supplied credentials and LoginResponse included a valid UID. The email
App UI took an email-verification-code path, so username login was used. No
Google credential was needed. A separate normal HTTP login using the provided
email/password also succeeded and queried three stations.

The current private login file was updated from the verified App request.
With App stopped and temporary proxy/trust setup removed, WazeProvider's
missing-UID path performed one HTTP login, followed by two successful searches
(three stations each). The second search reused the UID. This establishes a
working password-based alternative; it does not establish the previously
unverified web-Google-to-native token exchange or perpetual account validity.
Evidence: artifacts/waze/password-login-live-test.json.
