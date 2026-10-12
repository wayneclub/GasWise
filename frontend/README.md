# GasWise frontend

Mobile-first decision screen for the GasWise API: open it, and it answers which station is worth driving to for your car, fill amount and priority. Design and scope follow [the frontend plan](../docs/frontend-plan.md).

## Run

The dev server proxies `/api` to the backend and injects the service token server-side. The token is read from `frontend/.env.local` (`GASWISE_API_TOKEN=...`) or, if absent, from `backend/.env`. It never enters the browser bundle. Do not use a `VITE_` prefix for it.

```sh
npm install
npm run dev                                         # proxies to the live backend at http://127.0.0.1:8000
GASWISE_API_URL=http://127.0.0.1:8001 npm run dev   # e.g. a demo-mode backend
```

Synthetic data without quota: start the backend from the repository root, where no `.env` is loaded, so it runs in demo mode:

```sh
uv run --project backend uvicorn gaswise.main:app --port 8001
```

`.claude/launch.json` defines both (`backend-demo`, `frontend-demo`). In development the location error screen offers a downtown Los Angeles fallback for browsers without location access.

## Checks

```sh
npm test            # vitest: formatting, confidence, breakdown, request mapping, screen flows
npm run typecheck
npm run lint
npm run build
npm run gen:api     # regenerate src/api/schema.d.ts from contracts/openapi.json
```

## Languages

English, Traditional Chinese (zh-TW) and Spanish. The browser language picks the default (`zh-*` to Traditional Chinese, `es-*` to Spanish, otherwise English); Settings overrides it and the choice is saved with the preferences. Copy lives in `src/i18n/` with English as the source catalog; the other catalogs are type-checked for missing keys and tested for matching placeholders. Backend vehicle prompts are not shown verbatim: the picker translates by `answer_field` and enum values, while years, models and engine options stay as EPA data. Source opening labels such as "Closes 10 PM" are English upstream text, so other languages show the translated open/closed state instead. Prices stay in USD per US gallon.

## Location

GasWise uses the browser Geolocation API once per search; there is no address lookup. On first use it explains why before the browser prompt appears (the request starts from a tap). With permission already granted it locates straight away; when denied it explains how to re-enable it. Geolocation needs a secure context: `localhost` works, but a phone opening the dev server over a LAN IP needs HTTPS. The in-app preview browser in Claude Code always denies location, so development builds offer a downtown Los Angeles fallback.

## How it talks to the API

| User action | Request | Upstream cost |
| --- | --- | --- |
| Open app, Refresh | `POST /v1/smart/search` with `calculate_routes: true`, `route_limit: 10` | One acquisition and up to 10 routes |
| Change gallons, priority, payment, Costco, unconfirmed prices | `POST /v1/smart/rerank` with the held snapshot | None |
| Change vehicle or fuel | New search | One acquisition |

There is no polling, background refresh or GPS-driven re-search. The signed snapshot lives only in memory (it expires after 10 minutes; a 409 shows a refresh prompt). `localStorage` holds only preferences.

Priority maps to `time_value_per_hour`: Save money 0, Balanced 15, Save time 30 USD per hour. Confidence is derived client-side (`src/lib/recommend.ts`). Cautions are real gaps only: a price older than one day, unknown update time, disputed sources, unverified card/cash pricing, unconfirmed hours, or fewer than three comparable stations. A single source is neutral; agreement across sources and confirmed open hours show as positive signals. Anything below high relabels the pick "Best among verified prices".

The headline card shows the compared total as fuel purchase plus the fuel burned driving to the station (round trip, or the detour on a route), then money and time against the opposite extreme (quickest or cheapest) with the implied hourly rate.

## Design

Design read: a mobile-first decision tool for drivers about to refuel, trust-first and numeric, built with Tailwind v4 and hand-built components. Taste-skill dials: VARIANCE 3, MOTION 3, DENSITY 6. Warm ivory, light only, per product direction. One neutral family, ink for primary actions, sage for savings, amber only for limited confidence. Geist with tabular figures, Phosphor icons, no emoji or em dashes. Radius rule: containers 20px, controls 14px, chips full. Motion is limited to state feedback and respects `prefers-reduced-motion`.

## Production

A runnable same-origin gateway is included. With the backend on port 8000:

```sh
npm run build
npm start                  # http://127.0.0.1:4173
npm run test:gateway       # authentication, origin, traversal and rate-limit checks
```

`server.mjs` serves only `dist/`, proxies only the app's POST endpoints, injects the service token server-side, rejects cross-origin submissions, caps request bodies and applies 30 requests/minute per connection address. The token comes from the process environment, `frontend/.env.local`, then `backend/.env`; it never enters the bundle. Override `GASWISE_API_URL`, `HOST` or `PORT` explicitly. Local binding is the default. Public deployment requires an HTTPS reverse proxy and appropriate per-user access controls and quotas; this service-token gateway is not a multi-user identity system.

Location permission must be granted by the user in a supported browser. Loopback is a secure context; a phone visiting a LAN IP needs HTTPS. A responsive viewport test does not prove a physical phone GPS fix.

## Extended decision screen

- Payment includes All (`cash_or_credit`), Card and Cash. All compares known terms and retains the actual payment method on each price; unknown payment is a separate opt-in. Smart acquisition retains both GasBuddy cash/card variants with one source search.
- Google Maps is the default navigation app. Existing v1 test preferences are migrated once; later explicit navigation choices are preserved.
- Nearby station cards show confirmed-open discovered stations, including those without an eligible quote. Settings uses a separate page; the top location and vehicle context defaults to a compact summary. Backend coverage reports the exact representative quote and exclusion reason. Recommendation cards, comparison rows and nearby cards open a station detail sheet. Customer ratings and review counts are sourced separately from fuel-price confidence.
- On-route mode accepts destination coordinates in Settings and compares via-station routes against the direct trip. It searches near the origin, not the complete corridor. `smart/routes` can add costs to more eligible stations without acquiring prices again, up to 100 routes total.
- Vehicle selection accepts model text, VIN or US state/plate, with configuration confirmation when needed.
- The Parts tab searches AutoZone products by keyword and exact VIN/plate through `/v1/parts/search`, then checks each candidate against the vehicle. A second mode checks Amazon US product URLs through `/v1/parts/fitment`. Results distinguish verified fits, rejected products and cases needing confirmation; unavailable sources never become verified fits.
- Tabs keep the fuel session mounted, avoiding a new price acquisition when returning from Parts. VIN, plate and destination stay only in memory; saved preferences contain the EPA vehicle ID and general settings.

See [validation record](../docs/frontend-validation.md) for observed live results and remaining limits.

Fuel search samples five overlapping Maps website viewports inside an 8 km radius and compares every eligible station up to 100 routes. Closed and unknown-hours stations are excluded. Maps/GasBuddy responses remain bounded and cannot guarantee every station in the area.

Vehicle identification is managed in global Settings and reused by both tabs. Address/city/US ZIP lookup uses `/v1/locations/resolve` through Google Maps website HTTP search, explicit submit and bounded requests. It reuses the existing validated Maps session and does not call Places API or silently switch providers. Location and vehicle identifiers stay in memory. GPS permission is separate from successful coordinate acquisition; failures expose address/ZIP recovery. Destination settings accept the same location search.

Unspecified-payment quotes are included by default in the app. Credit/all-payment ranking applies the user-assumed $0.20/gal adjustment; cash mode adds none. `price_per_gallon` and evidence remain the original source quote, while `comparison_price_per_gallon` and `payment_price_adjustment` identify the estimate. This is not evidence that a station accepts cards or charges that surcharge. Users can disable estimated quotes in Settings. TOP TIER uses a compact text badge, not a large logo.
