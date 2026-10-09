# AAA API integration research

Researched 2026-10-09. Scope: AAA daily regional averages and a possible licensed retail-price replacement. No account creation, vendor contact, purchase, or application behavior changes performed.

## Findings

No public official AAA fuel-price developer API documentation, API-key registration, or supported JSON lookup contract was found in the reviewed official sources. This does not rule out private partner access. AAA describes its public service as daily national, state and local averages updated by OPIS in cooperation with WEX.

- AAA methodology: https://gasprices.aaa.com/about-aaa/
- State averages: https://gasprices.aaa.com/state-gas-price-averages/
- California and metro averages: https://gasprices.aaa.com/?state=CA

GasWise already exposes `GET /v1/sources/aaa/averages?state=CA` with Bearer authentication. `backend/gaswise/providers/aaa.py` retrieves and parses public HTML. County regular averages use the page-observed `index.php?premiumhtml5map_js_data=true&map_id=...` resource; this is a website implementation detail, not a documented developer API. Do not hardcode map IDs or treat that endpoint as a supported API contract.

Direct provider verification on 2026-10-09 returned source date 2026-10-09, 32 regions (one state and 31 metros), and `county_status=unavailable`. This confirms live state/metro retrieval only; it does not establish reliable county availability or deployed-service health.

## Official commercial route

OPIS offers retail station prices, custom regional averages and data feeds, with trial/demo options:

- https://www.opis.com/product/pricing/retail-fuel-prices/
- https://www.opis.com/product/pricing/retail-fuel-prices/pricepro/
- https://info.opis.com/submit-prices?hsLang=en

Public PricePro API wording includes POS integration and volume imports. It does not establish a publicly accessible consumer station-price lookup API. Obtain the actual licensed export/query specification before implementing a provider. A custom OPIS average is not necessarily identical to AAA's published average.

The published OPIS Rack API is wholesale pricing and is not a replacement for retail pump prices: https://www.opis.com/product/pricing/fuel-rack-prices/rackapi/

## Recommendation for GasWise

Keep the existing AAA adapter for daily regional context. Clients can already consume JSON through GasWise rather than parse AAA themselves. Preserve `price_as_of` separately from `retrieved_at`; fetching now does not make the underlying price current. County failure must remain explicit. Daily averages must not enter individual-station price rankings.

For an official licensed replacement, request these details from OPIS before selecting an integration:

1. Retail station quotes versus AAA-equivalent regional averages; California/Los Angeles coverage.
2. API or file delivery, authentication, query parameters, pagination, limits, and sample response.
3. ZIP/radius search or station coordinates and stable IDs.
4. Cash/credit distinctions, membership conditions, numeric octane (91/93) versus Premium labels.
5. Price observation timestamps, refresh frequency, stale/missing-price handling and coverage metrics.
6. Consumer-app display, caching/history, redistribution rights, trial access and total pricing.

For station quotes, adapt verified vendor fields into the existing `gaswise.price-feed.v1` contract (see `docs/price-source-integration.md`). For regional averages, use a separate regional-average adapter. Do not invent vendor URLs, authentication or fields before receiving documentation. Third-party AAA scraper APIs add an intermediary and do not establish official AAA access or faster underlying updates.
