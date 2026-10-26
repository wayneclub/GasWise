# Waze HTTP integration

Waze is opt-in and uses private native-protocol credentials. On 2026-10-10,
normal App username/password login and direct HTTP email/password login were
both verified with the owner's configured Waze password. The current private
login request now uses that password, rather than the earlier Google-linked
bootstrap credential. App, ADB, browser, proxy and Google login are not required
for HTTP UID renewal while this Waze account/password remains accepted. Web
Google sign-in exchange remains unverified and is not used by this flow.

Set `GASWISE_WAZE_ENABLED=true` in `backend/.env`, use `prices_only` or `google`
mode and keep `GASWISE_API_TOKEN` configured. The current workspace's private
configuration now enables Waze. Restart a running API process to load it.

Default private files (never commit or send them):

- `~/.config/gaswise/waze-http-session.json`: active UID.
- `~/.config/gaswise/waze-http-login.bin`: authorized login request, containing credentials.
- `~/.config/gaswise/waze-http-login-headers.json`: functional login headers.

Override with `GASWISE_WAZE_SESSION_FILE` and `GASWISE_WAZE_LOGIN_FILE`, using
absolute paths. `GASWISE_WAZE_AUTO_LOGIN=false` disables automatic HTTP login.
These files must be provisioned securely when deploying to another machine.

## API

All endpoints require the existing GasWise Bearer token.

`POST /v1/sources/waze/prices` returns all fuel types, station address/ZIP,
coordinates, per-fuel update timestamps and updater. Request:

```json
{
  "origin": {"lat": 34.0833736, "lng": -118.3008564},
  "radius_meters": 5000,
  "max_results": 5
}
```

Optional `venue_id` selects a Waze venue such as
`venues.158400853.1584008528.5847665`. `postal_code` filters returned stations;
it does not geocode a ZIP or guarantee complete ZIP coverage.

`POST /v1/prices` includes normalized Waze prices in the source registry.
Choose `fuel_type` (`regular`, `midgrade`, `premium`, `diesel`) with the existing
Search schema. `POST /v1/smart/search` also includes Waze; in prices-only mode,
set `calculate_routes:false`. Waze provides prices, not route calculation.
Capabilities and source discovery expose enabled state without credentials.

## Session lifecycle and failure handling

A missing session triggers one normal HTTP login if enabled. An explicit
upstream relogin error triggers at most one login and one repeated search.
An async lock serializes this per adapter, preventing concurrent refresh storms.
HTTP 429 or the native login RATE_LIMIT_FAILURE produces `waze_rate_limited`
and a 120-second local cooldown. Authentication rejection produces
`waze_reauthentication_required`; no Google-login automation is claimed.
Upstream bodies, UID, usernames, password and login file paths are not exposed
in API error details. A saved UID is atomically replaced with permission 0600.

Prices are US-only. Payment type and numeric octane remain unknown; Premium is
not claimed as verified 91. E85 is available in the raw endpoint but excluded
from the current four-fuel normalized model. Price update time is separate
from fetch time. The adapter uses an undocumented protocol, not a public API.

## Verification

The live test began without a saved UID. HTTP login succeeded, followed by 200
responses from all three endpoints: raw (3 stations), normalized (3 quotes),
smart (19 Premium quotes, one Waze search, no Google/GasBuddy calls in the
isolated test configuration). Public results: `artifacts/waze/backend-live-test.json`.
Automated tests cover expired UID refresh, bounded retries, cooldown, credential
redaction, fuel mapping, timestamps, ZIP filtering and API access protection.


## Password login verification (2026-10-10)

The App's email entry used an email-verification-code flow; entering the
account's existing username instead exposed normal password login. Login with
the owner's newly configured password succeeded and returned a native UID.
The captured successful password login request was installed in the existing
private login file. Separately, normal HTTP login with the account email and
the same password succeeded and returned three stations.

With Waze force-stopped, proxy reset to :0, temporary certificate mount removed
and adbd restored to non-root, the actual WazeProvider was tested without a
saved UID. It performed one HTTP login and two searches, each returning three
stations. The second search reused the issued UID. Evidence:
`artifacts/waze/password-login-live-test.json`. Credentials and UID are excluded.

This verifies current password-based UID renewal, not perpetual credential
validity. Changing the Waze password requires securely updating the private
login request. Account rejection or a new verification requirement still
produces reauthentication_required; no bypass is attempted.


## Station details and grade estimates

Raw prices and normalized Station now preserve `details`: brand, phone, website,
description, service IDs/labels, credit-card acceptance, weekly hours, timezone,
computed open_now and its evaluation timestamp. Unreported services remain
unknown, rather than false. A credit-card service flag never changes a quote's
unknown payment_type. Weekly hours handle overnight intervals and Sunday=0;
a source-declared 00:00–00:00 interval means 24 hours. Open status is unknown
without usable hours/timezone, and exceptional hours invalidate weekly inference.
Temporary/permanent business closure overrides an otherwise open schedule.
Google rating, rating count, business status and price-level metadata are
retained under google_attributes, attributed to google_via_waze. Price level
is a general business indicator, not fuel price or cash/card classification.

`octane_inference` carries AKI scale, regional estimate, brand range, source
URLs, check date and station_verified=false. California typical grades are
87/89/91 from CEC's October 2021 Petroleum Watch. State is used when present;
otherwise a California postal-code range supplies an explicitly labeled
regional inference. These historical regional definitions do not verify every
pump. Shell US ranges are 85–87 / 88–90 / 91–93 from its official fuel page;
Sinclair Premium 91–93 is backed by its 2025 official promotion. Plus aliases
Midgrade; Supreme/Super alias Premium. Diesel/E85 have no gasoline-grade
inference. Unknown brands outside the regional table remain unknown.
The pump-verified `octane` stays null, so strict octane ranking never silently
accepts estimates. Rules live in gaswise/domain/pricing/grades.py.

Live response evidence: artifacts/waze/station-details-live.json. Hours are
source reports; calculated open_now is not an independent real-time check.

## Login header repair (2026-10-26)

Captured functional headers use lowercase names. Login previously filtered them
into a case-sensitive dictionary and then added title-case defaults with
`setdefault`. This emitted duplicate User-Agent, Content-Type and network-version
headers and the native login endpoint returned HTTP 400. Login now builds an
`httpx.Headers` collection before adding defaults, so existing names match
case-insensitively. The original account credential and captured request body
remain unchanged. A bounded production test with the corrected adapter logged
in over HTTP, returned 15 stations / 51 fuel quotes and installed only the
verified UID. No account password change or App runtime was needed.

Shared query caching now retains a sanitized failure code for 30 seconds. A
second process encountering a failed cold-query owner returns that source's
failure immediately, rather than waiting twenty seconds for a payload that will
not arrive. Usable stale observations remain separately available with original
timestamps; failure is never saved as successful price data. Success clears the
failure, expiry permits another bounded acquisition, and other sources keep
their own results. The UI explicitly names sources whose prices remain available.
