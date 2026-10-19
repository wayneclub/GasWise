# Frontend integration validation — 2026-10-11

Validated locally against the live backend at 127.0.0.1:8000, Vite at 5173, and the production build with its same-origin gateway at 4173. Public downtown Los Angeles coordinates and a sample vehicle identity were used, not the user's precise location or identifiers. Public deployment was not requested.

## Implemented flows

- Payment All, Card and Cash retain the actual quote terms. Unknown payment remains a separate opt-in; ratings and credit-card amenities cannot establish payment eligibility.
- Google Maps is the default navigation choice. Later explicit choices are preserved.
- Fuel and Parts tabs preserve the fuel session without reacquiring prices when switching tabs.
- Vehicle model, VIN and US state/plate lookup expose configuration confirmation and unavailable results.
- Parts keyword search finds AutoZone products and verifies each exact candidate against the decoded vehicle. Amazon product-link fitment remains a separate mode. Conditional or unavailable evidence is never labeled a verified fit.
- Recommendation cards, comparison rows and nearby inventory cards open station details with address, sourced rating/review count, payment, price evidence, opening information and available phone/website/services.
- Nearby inventory explains exclusions and coverage. On-route mode compares direct and via-station costs using destination coordinates; discovery remains near the origin rather than along the whole corridor.
- Signed-snapshot reranking cancels superseded requests. Additional routes use existing prices; expired costs retain their original gallons label.

## Evidence

- Frontend: 41 Vitest tests passed; TypeScript, lint and production build passed.
- Local gateway: 6 tests passed for authentication injection, origin/method/content restrictions, traversal and rate limits.
- Backend: 510 tests passed, with a pre-existing Starlette/httpx deprecation warning.
- Live production gateway search: 32 discovered stations, 27 with prices, 2 eligible under strict payment conditions. Explicitly including unknown payment allowed 9 routed candidates. Counts and prices vary by source and time.
- Expanding from 1 route to 9 added 8 route calculations with zero GasBuddy/Google nearby acquisition calls. Preference reranking also made zero upstream calls.
- Live keyword parts search checked 6 candidates and verified 3 fits in 2.82 seconds; 3 required further confirmation. Source: AutoZone. Amazon live fitment returned an unresolved result when its source was unavailable.
- Browser exercised vehicle selection, VIN/plate entry, payment/settings, tabs, generic parts results, on-route settings, station drawers and comparison. Responsive 390×844 viewport was checked.
- Safe production summary: `artifacts/frontend-validation/production-smoke.json`; browser screenshots in that directory.

## Validation limits

Physical phone GPS and external navigation app launch were not exercised. Development browsing used the public location fallback. A phone accessing a LAN IP needs HTTPS for geolocation. This is a local runnable build, not proof of public deployment or every upstream provider's availability. Station ratings without source data show unavailable rather than an invented score.

## Shared settings, location and navigation revision

Vehicle model, VIN and plate now live in global Settings, accessible from both tabs. Parts consumes the shared session identity. Editing a vehicle preserves the current selection until a replacement resolves; a decoded identity without an EPA match can serve parts while fuel uses manual settings.

The header combines brand, compact underlined tabs and Settings. Audit: retire oversized detached tabs and duplicate headers; preserve Geist, Phosphor, warm neutrals, sage accent and data cards. Applied contextual principles from https://github.com/Leonxlnx/taste-skill/blob/main/skills/taste-skill/SKILL.md with DESIGN_VARIANCE=3, MOTION_INTENSITY=2, VISUAL_DENSITY=5.

Location errors distinguish denied, unavailable and timed out. Permission does not guarantee a coordinate. Address/ZIP search is available in the failure state, normal location control and destination settings. Choose a candidate before use; ZIP searches use an area center.

Google Places Text Search returned `google_quota_or_rate_limit_exceeded` in live testing. The initial revision used Photon. The final adapter now reuses Google Maps website HTTP search and the validated private session, with explicit submit, five candidates and at most one request/second. It has no autocomplete, polling or automatic provider fallback.

Live proof: ZIP 90015 resolved to Los Angeles and completed a fuel search with 31 discovered stations and four eligible cost comparisons. The public Los Angeles City Hall street address also resolved. The 390×844 viewport had document width 375 with no horizontal overflow. Screenshot: `artifacts/frontend-validation/navigation-location-mobile.png`. Physical phone GPS remains untested; this does not prove the cause of the user's earlier device failure.

Current checks: 44 frontend tests, 6 gateway tests and 517 backend tests passed; TypeScript/lint/build passed. Shared identity and timeout-to-ZIP recovery have explicit integration tests.

## Google Maps website location proof

Observed `/search?tbm=map` array rows expose coordinates at field 9 indices 2/3, display name at 11, place ID at 78 (fallback identity at 10), and explicit country at 183/1/6. The existing `records` walker is reused. The location parser requires US metadata, valid coordinates and an identity; malformed rows are skipped, duplicates removed and output capped at five. It preserves Maps transport errors for rate limits, rejected sessions and unexpected responses. This is an observed private website protocol, not a guaranteed API.

Live ZIP 90015 returned `Los Angeles, CA 90015` at 34.0390107, -118.2672801. The public address 200 N Spring St, Los Angeles, CA returned its street address at 34.0539774, -118.2426185. Both used one website HTTP request each and zero Places API calls. The same-origin production endpoint at 4173 returned `source=google_maps_web`. Browser lookup and selection were exercised; screenshots: `google-web-location-mobile.png` and `google-web-fuel-mobile.png`. Current browser GPS attempt timed out; manual lookup remains usable.

Identical successful lookups reuse a two-minute memory-only cache of at most 32 entries with hashed query keys. No raw address query or session credential is written to disk. Redirect/challenge bypasses and automatic paid fallbacks are absent. Regression checks verify the fixed Google host/path, no API key header, zero-network cache hit, invalid-session stop, and explicit 403/429/unexpected-response failures.

## Location controls and search context revision

The search context is now a labeled section: search area, location source, explicit device-location and address controls, vehicle edit, fuel grade, payment condition and a separate text-labeled price refresh. Initial permission requests use an inline address form rather than a duplicated large error screen. Mobile stacks the area and vehicle; desktop displays two aligned columns.

Live inspection of the actual 5173 browser origin confirmed a secure context and an available Geolocation API; its Permissions API initially reported `prompt`. Permission is origin-specific. A user-triggered request now starts `getCurrentPosition` synchronously from the tap before awaiting Permissions API; it requests high accuracy and allows 60 seconds. An unsuccessful request preserves the previous manual area and fuel result. A still-pending permission is distinguished from device timeout. Regression checks cover a stalled permissions query and GPS failure after a manual selection. Frontend: 46 tests passed; lint and build passed. No geolocation override or simulated coordinates were applied to the live browser.

Live GPS follow-up: the user confirmed the same built-in browser can locate in Google Maps and reported selecting Allow for this app. A stable page request, without further hot reloads, still returned no coordinate within 60 seconds and Permissions API remained `prompt`. The origin was `http://127.0.0.1:5173`, secure context true, Geolocation API native, top-level frame true, and geolocation policy allowed. The browser control bridge does not support `Browser.setPermission`; its attempted synchronization made no permission change. Root cause is not established, and actual device geolocation must not be reported as verified. The previous manual location and fuel result remained available after failure.

Screenshots: `artifacts/frontend-validation/search-context-mobile.png` at 390×844 and `search-context-desktop.png` at 1100×850. These screenshots use the public ZIP test location, not the user's GPS coordinates. No app, OS or browser-wide security settings were changed.

## 2026-10-11 — expanded open-station search and compact UI

- App fuel search now requests five overlapping Maps website viewports in an 8 km radius, deduplicates identities, and requests up to 100 routes/results. The source responses remain bounded; this is not proof of every station in the area or a global optimum. Routing compares every eligible discovered station when routes succeed. Closed and unknown-hours stations are excluded from recommendations and the open-station card list. Coverage distinguishes discovered, priced, eligible, routed and displayed counts.
- Live public ZIP 90015 check found 36 station records, 30 with a selected-grade quote, and 34 explicitly open. The old working session initially had estimates disabled; enabling them and expanding routes without reacquiring prices produced 11 eligible stations and 11 cost comparisons. Eight additional unknown-payment candidates were included. Prices older than the configured 24-hour limit, unavailable selected grades, and closed/unknown-hours records remain excluded.
- Unknown-payment prices are included by default in the app, with a user-assumed $0.20/gal adjustment for credit/all-payment ranking. Raw source prices and payment type remain unchanged. Estimated comparison price, adjustment, cost and break-even calculations are consistent. A repeated rerank does not compound the adjustment or call upstream services. The estimate does not establish actual card acceptance or surcharge. Cash mode applies no adjustment; Settings can disable these estimates.
- Settings is a full page, retaining the mounted fuel/parts sessions. The context is a two-row summary with vehicle details collapsed by default. Coverage is a numeric grid; cost comparison has compact bars and estimate labels. Vague confidence badges and long top-card reason paragraphs were replaced with specific short signals. TOP TIER is a small shield/text badge. Long configuration choices wrap in full-width buttons with stable accessible names.
- Validation: 538 backend tests, 54 frontend tests, six gateway tests; TypeScript, lint and production build passed. New tests cover overlapping discovery/deduplication, more than ten eligible routes, closed/unknown exclusions, partial rate-limit recovery, preserved raw prices, no compounded surcharge, settings-page navigation/session preservation and the compact badge. The production gateway on port 4173 serves the current build and forwards malformed authenticated API input to a 422 validation response.
- Browser checks at 390×844: document client/content width both 375 px (scrollbar excluded), settings has no dialog, fuel comparison shows all 11 eligible stations, estimated rows preserve source quotes in details, and TOP TIER has no large image. The long configuration-label regression test resolves the selected vehicle without persisting VIN.
- GPS remains unverified: no real device coordinate was obtained in the earlier Codex browser test. Address/ZIP lookup is working. No GPS, security or OS settings were changed.

Screenshots: `artifacts/frontend-validation/estimated-comparison-mobile.png`, `settings-page-mobile.png`, and `compact-fuel-mobile.png`. These use public test locations and vehicle model names.

## Recovering a suspended browser tab

Fuel searches now keep a versioned recovery record in `sessionStorage` for up to
30 minutes after the last check. The record contains the signed result, search
origin, manual location label, and search/ranking settings. It is scoped to the
browser tab; locations and price snapshots are not copied to `localStorage` or
synced between browsers. VIN/plate identity storage is unchanged.

A matching record restores results immediately on page reload without another
location request. Existing visibility-based polling checks prices in the
background after two minutes; expired snapshots trigger an immediate background
check on recovery and retain an expired label if the check fails. Original
source and collection timestamps are preserved. Mismatched settings, expired
recovery records and corrupt storage are discarded. Blocked storage falls back
to the existing in-memory behavior. Route destinations can be recovered from
the same temporary record rather than retained in long-lived preferences.

Automated checks simulate unmount/remount, expiry, offline refresh failure,
changed fuel, corrupt or blocked storage, and recovery TTL. Physical iOS/Android
OS tab eviction has not been exercised.
