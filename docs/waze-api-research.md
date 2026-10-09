# Waze integration research

Researched 2026-10-09. No Waze account access, mobile station-price validation, partner application, or provider implementation performed.

## Live investigation on 2026-10-09

Playwright follow-up (user explicitly requested browser fallback): stock locally installed Chrome in a fresh anonymous context, no stealth/fingerprint modification, no imported profile/cookies. Headless editor navigation returned 200; practice UI readiness timed out, and the context's ordinary HTTP fuel request returned 403. A separate headful probe to the English editor returned 502 before any fuel read. These results do not establish that login is necessary, that Selenium would behave differently, or that browser automation cannot ever read fuel prices. The in-app browser had already demonstrated anonymous practice-mode search success. A reproducible diagnostic is `uv run python ../scripts/check_waze_browser.py --headful` from `backend`; it is not registered as a price provider. Ruff passed. Neither browser probe retrieved a fuel quote. Community script source last commit at inspection was 2026-03-01, so the lead is not merely an abandoned 2018 example; nevertheless its current fuel endpoint remains unverified in this environment.

Pure HTTP/2 follow-up using the same approach as `GasBuddyHTTPSession`: one fresh httpx client, ordinary landing requests, shared in-memory cookie jar, and normal editor referer. Both Waze homepage and editor returned 200 over HTTP/2, no CSRF marker and no cookies at that point. A venue fuel request with the client-declared `origin=editor` returned 403. The editor source's normal `/Descartes/app/Session?language=en` bootstrap endpoint returned 403 JSON and set two cookies; bootstrap rejection was not treated as authenticated access. Unlike GasBuddy, this tested flow did not provide a successful anonymous session/API request. No browser-cookie import, challenge solver or token fabrication was used. Reproduce from `backend` with `uv run python ../scripts/check_waze_fuel.py --http-session`.

Follow-up: a fresh normal browser request to the US `SearchServer/mozi` fuel URL also returned 403. The editor subsequently loaded successfully at `/editor`; entering its ordinary practice mode enabled location search without signing in. Its actual UI search returned HTTP 200 from `/Descartes/grpc/com.waze.mapeditor.web.api.MapEditorWebServer/searchLocations` (gRPC-Web encoded response), rather than SearchServer. The current editor client still contains the US SearchServer configuration, but no fuel-price rendering fields were found in the inspected application bundle. Successful location search is not successful fuel retrieval. The prior editor 502 was transient and is no longer the current blocker. Signed-in access has not been tested and is not known to fix the fuel endpoint.

The public Live Map successfully found 76 at 4600 Melrose Ave, Los Angeles. Browser network inspection returned HTTP 200 for `/live-map/api/venues/158400853.1584008528.5847665?locale=zh-TW`. Its JSON included name, address, coordinates, phone, hours, images and services, including `credit_cards`, but no fuel prices. Accepting credit cards is not evidence of a credit-price quote. Direct unauthenticated HTTP requests to the venue and autocomplete endpoints returned 403 in this environment.

Read, but did not install or execute, the source of the community WME BackEnd Data script:
https://github.com/TheCre8r/WME-BackEnd-Data/blob/master/WME-BED.user.js

It constructs a SearchServer request with `format=PROTO_JSON_FULL` and `venue_id=venues.<id>` and reads `venue.product` entries containing `gas.*`, `price`, and `last_updated`. A WazeWrap source example supplies the US path `/SearchServer/mozi`:
https://greasyfork.org/en/scripts/471457-wazewrap-testing/code

A direct read-only request for the verified 76 venue to that endpoint returned HTTP 403, not fuel data. The editor page also failed to load (browser 502). No price, freshness, cash/credit or numeric-octane acceptance has been verified. These community scripts establish an implementation lead, not a supported API or current access entitlement.

Reproduction: `python3 scripts/check_waze_fuel.py`. This standalone diagnostic uses no credentials, cookies, challenge handling or retries, and is not connected to the production source registry. Source rejection exits nonzero and reports `prices_verified=false`. A future permitted session or partner integration would still require current response validation before adding a price provider.

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

Keep AAA regional averages and station quotes separate. Add Waze navigation only when requested. If fuel-price access is important, ask Waze product partnerships whether a commercial consumer-app fuel export is available and obtain the schema, pricing, station coverage, timestamps, payment conditions, numeric octane and display/cache rights before implementation. OPIS retail data licensing is a more directly documented route to investigate for the upstream feed.
