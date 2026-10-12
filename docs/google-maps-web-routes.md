# Google Maps website road routes

`GASWISE_MAPS_WEB_ROUTES_ENABLED=true` enables an independent HTTP directions
provider in live mode, including `prices_only`. It uses Google Maps website
directions, not the billed Google Routes API. No Google API key is required.
The GasWise bearer token is required. The existing paid Routes switch stays
independent; the website provider takes precedence when explicitly enabled.

Runtime performs **two HTTP requests per logical route**: the Maps driving page,
then the fixed `/maps/preview/directions` preload URL returned by that page.
All requests stay on HTTPS `www.google.com`. Only a relative directions preload
is accepted. Redirects, rate limits, challenges, malformed data and waypoint
mismatches fail without retry, straight-line estimates or paid API fallback.
The configured authorized Maps session is reused when present; anonymous
directions were also verified. No browser is needed at runtime.

## Cost and time provenance

Driving mode was verified through the Maps interface (`!3e0`, response mode 0).
Responses may contain other travel modes; those cannot enter driving ranking.
The provider selects Google's first recommended driving route. It validates the
ordered echoed coordinates for every requested stop before accepting any total.

Numeric route distance is read from the route summary `[2][0]` in meters.
Current traffic estimate, when supplied, is read from `[10][0][0]` in seconds;
otherwise the base estimate `[3][0]` is used and labeled `maps_estimate`.
Observed response path is `[0][1][driving route][0]`. Rounded display labels are
never parsed into numbers. `Route` exposes `source=google_maps_web_directions`,
`duration_basis`, `fetched_at` and `upstream_http_requests`.

Round trips request origin → station → origin as one multi-stop route; outbound
distance is not doubled. On-route trips request origin → destination as baseline,
then origin → station → destination, subtracting only additional miles/time.
The same source station crosswalks and strict payment/membership/octane eligibility
used for prices remain in force.

**Fuel is estimated from user MPG, not measured by Google Maps.** Ranked rows
expose `mpg_used`, `detour_fuel_gallons` and
`fuel_consumption_basis=user_mpg_estimate`. Formula remains extra road miles / MPG,
valued at station price. Time, traffic, stop duration and real-world consumption
are estimates; queue, toll, wear and segment-specific fuel economy are excluded.

## Request discipline

`upstream_calls.routes` counts logical baseline/candidate route attempts.
`upstream_calls.maps_web_route_http_requests` counts actual attempted website HTTP
requests, including failed attempts. Snapshot reranking performs zero upstream
calls and preserves route collection time. Discovery and traffic are not an atomic
snapshot. Existing candidate limits apply; this is the best among a bounded
eligible shortlist, not a full-corridor optimum.

```text
GASWISE_MODE=prices_only
GASWISE_MAPS_WEB_ROUTES_ENABLED=true
GASWISE_GOOGLE_ROUTES_ENABLED=false
```

Keep the existing authorized price-source/token configuration and restart the
backend. `/v1/capabilities` reports the actual selected `routing_source` and
`smart_routes_enabled`. The running local service was restarted with this
configuration on 2026-10-10. Use smart search/routes/rerank for bounded acquisition;
legacy recommendation endpoints perform their separate price acquisition.

```sh
cd backend
uv run python ../scripts/smoke/smoke_smart_search.py --routes --trip-mode on_route --maps-detail-limit 0
```

This explicit live smoke refreshes each price source once and acquires at most one
baseline plus two candidate routes (six website HTTP requests). It prints diagnostic
counts and derived costs; it saves no price/route history.

## Evidence and acceptance on 2026-10-10

- Anonymous directions for the DTLA example returned 3,155 meters, base duration
  641 seconds and traffic duration 529 seconds. The Maps interface showed driving,
  2.0 miles and 9 minutes, supporting the traffic field choice rather than the
  11-minute base field. Values can change on later requests.
- A native three-point round trip echoed all requested stops and returned 4,505
  meters / 640 traffic seconds. A separate on-route provider request returned
  6,192 meters / 712 traffic seconds. These were real road routes, not geodesics.
- Integrated Premium/credit on-route smoke returned all three price sources `ok`,
  baseline 3,155 meters, and two ranked candidates. Speedway Express via-route was
  8,014 meters / 906 seconds, detour 3.019 miles, estimated 0.150962 gallons at
  20 MPG and total fuel cost $64.86. ARCO via-route was 9,817 meters / 749 seconds,
  detour 4.140 miles, estimated 0.206979 gallons and total $65.22. This covers two
  routed candidates, not all eligible stations or pump-price accuracy.
- The final on-route smoke attempted one search per price source, zero Maps price
  details, three logical routes and six website route HTTP requests. Official
  Nearby, Text Search and paid Routes calls were zero.
- After restarting the actual localhost:8000 service, capabilities reported
  website routing enabled. A round-trip HTTP search returned ARCO's native route
  at 6,083 meters / 706 traffic seconds, estimated 0.188990 extra gallons at
  20 MPG and total fuel cost $65.11 among the single routed candidate. Reranking
  that signed response to 25 MPG returned HTTP 200, 0.151192 estimated gallons,
  and zero upstream calls. The round-trip search used one logical route / two
  website HTTP requests; it made no paid Google calls.
- Automated tests use two sanitized observed fixtures, preserving echoed points
  and numeric summary paths while omitting identities, tokens, steps and unrelated
  data. Coverage includes transit exclusion, invalid/nonfinite values, wrong/missing
  stops, hostile preloads, failure attempt counts, no retries, independent live-mode
  configuration, baseline subtraction and zero-call reranking.

REA retained-capture evidence:
`ev_c6a7466b2fbed70dca78bf0872ba1459afd253cf93bd73ee66fe0c2cac377df8`.
The capture contains decoded anonymous HTTP response JSON reserialized into HAR;
its timestamp marks assembly, not request time. Headers/cookies were omitted.
REA verified the retained producer record, not browser transaction attribution or
live execution. Browser visible state and separate live HTTP probes establish the
runtime observations above. This is an undocumented website protocol and can change.

[Official Maps URLs](https://developers.google.com/maps/documentation/urls/get-started)
documents launching driving directions and waypoints. It does not document this
numeric website response protocol or guarantee fuel-consumption precision.
