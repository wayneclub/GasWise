# Parts fitment API

`POST /v1/parts/fitment` accepts an Amazon US product URL and exactly one `vin` or `plate` identity. Local API authentication remains applicable; upstream public AutoZone requests require no account, key or browser cookies.

```json
{"amazon_url":"https://www.amazon.com/dp/B019IPTB0W","plate":{"state":"CA","plate":"YOURPLATE"}}
```

Use `"vin":{"vin":"YOUR17CHARACTERVIN"}` instead of `plate` for VIN lookup. Optional brand/part hints are unverified unless they agree with the selected Amazon ASIN's labeled fields. An optional canonical `oreilly_product_url` can narrow retailer discovery.

## Dynamic resolution

Amazon identity uses selected ASIN echoes, labeled brand, manufacturer part number and model number; MPN and model remain distinct. This is generic parsing, with live MANN and Bosch product evidence, rather than a per-brand part database.

AutoZone searches observed identifiers, follows returned taxonomy to product shelves, and requires one exact brand/part SKU. Plate lookup preserves supplier ACES configuration in memory; VIN requests obtain it directly. The native product endpoint receives engine and other vehicle IDs and must echo the exact SKU plus `VEHICLE_SPECIFIC` / `FITS` before compatibility is confirmed. Restrictions or outstanding application questions suppress confirmation. No old part number or manual housing inspection is requested by the normal API flow.

MANN manufacturer applications and O’Reilly public product/compatible-makes/compatible-models endpoints supply additional evidence. Fuzzy search hits, cross references without an exact identity, empty responses, and blocked requests cannot establish compatibility. Broad year/make/model matches alone remain unconfirmed. Conflicting sources return `conflict`.

Response evidence includes source, status, verification scope, observed SKU and restrictions. `compatible` requires verified Amazon identity, valid vehicle decode and strong application or native vehicle fitment evidence. This verifies catalog fitment, not physical inspection or installation quality. Missing supplier coverage may return `needs_confirmation`; it does not mean incompatible.

## Current validation (2026-10-10)

The authorized 2018 E400 Coupe plate and Amazon B019IPTB0W now return `compatible`, `identified`, `vehicle_fitment`, with AutoZone native `FITS` and manufacturer application agreement. A different STP S45023 SKU with the same VIN-derived configuration returned native `DOES_NOT_FIT` in the live protocol probe. No VIN or plate is retained in evidence artifacts.

O’Reilly's anonymous browser flow resolved the E400's engine from plate and returned `COMPATIBLE` for K&N HP7040 and `INCOMPATIBLE` for WIX 57060. Fresh pure HTTP reproduction still encounters challenge/429 responses. The backend O’Reilly adapter is connected for supplementary public application discovery, but its selected-vehicle checkfit flow is not claimed as production HTTP success. Its current failed lookup is reported as unavailable and does not override AutoZone proof. See `artifacts/oreilly-research/` and `artifacts/autozone-parts-research/`.

Configuration: `GASWISE_PARTS_SOURCES_ENABLED=true`, `GASWISE_PARTS_HTTP_TRANSPORT=curl` (default). Curl uses an anonymous Chrome transport with fixed host boundaries and bounded reads. AutoZone/Amazon/manufacturer reads use fresh per-request sessions. O’Reilly uses one fresh session per assessment, retaining only server-issued anonymous cookies within that operation; it does not replay browser/account cookies or follow redirects. Tests use isolated httpx mock transports.

## Product application and retailer substitutions

Store brands are not required to have identical names or part numbers across retailers. The requested Amazon product's identity and vehicle fitment are evaluated independently from each store's inventory. `cross_check.status` is now `supported`, `rejected`, `conflict`, or `insufficient`; it is not a two-retailer quorum. One native exact-product fit can support the requested product. Another retailer's unavailable inventory or unverified substitution does not downgrade that result.

Evidence labels `product_relation` as `direct_product` or `interchange_candidate`. Native decisions for different replacement candidates are not automatically conflicting decisions about the Amazon product. A rejected replacement candidate does not reject the original. Interchange links retain their source URL, referenced part number and candidate manufacturer's identity, and candidates still need their own application verification. Source-count metadata is informational.

O’Reilly discovery now falls back dynamically to GET `/interchange/getPartTypes`, POST `/interchange/getManufacturers`, then `/search/cross-reference`. The first two APIs succeeded with fresh pure HTTP for HU7025Z and OE2761800009. The final HTML result still returns a protection page, so the current backend does not fabricate replacement SKU records from the manufacturer list. It records successful lookup stages and the remaining unavailable results.

Anonymous browser observation of O’Reilly's native HU7025Z/Mann + Hummel interchange page showed MicroGard MGL57059, K&N HP7040, WIX57059, Mobil1 M1C352A and MicroGard Select MSL57059. This establishes supplier interchange candidates, not automatic vehicle fit. No fixture part table is used by production discovery. The supplied air/oil-separator category was also tried through HTTP: status200, 7433bytes, protection scripts and no product cards; browser navigation showed the actual industrial separator category. It is not engine-oil-filter fitment proof.

The 2026-10-10 fresh HTTP investigation successfully loaded `/` and POST `/header/data` with normal server-issued anonymous cookies, without a browser or login. In that same session, `/vehicle/plate/...`, `/garage/add`, and `/product/compatible-makes` still returned 429 `cpr_chlge`. This isolates the unresolved block to protected vehicle/application endpoints rather than basic anonymous session creation. No challenge tokens or browser cookies were replayed. Evidence: `artifacts/oreilly-research/anonymous-bootstrap-http.json`, `anonymous-vehicle-http.json`, `warmed-native-http.json`. Pure HTTP O’Reilly native fitment remains unresolved.

The public comparison endpoint `/pcp/compare-items?compares=<LCIN,...>` now validates discovered candidate identities dynamically, with at most four per request (the native API returns empty for five). Only line/part pairs observed in supplier cards are requested; returned identities must match. This endpoint succeeded through anonymous HTTP for all five observed interchange candidates. It supplies product names, not a mapping or vehicle fitment verdict. Pure HTTP replacement-list discovery and protected selected-vehicle fitment are still unresolved; do not claim end-to-end O’Reilly fitment from these three working JSON methods.

## Anonymous session and remaining browser verification

The O’Reilly transport now obtains `window._ost.csrfToken` from its own fresh HTTP homepage, retains only that operation’s server-issued anonymous cookies, and sends its CSRF value on JSON requests. Tokens are cleared when the operation closes; no login, browser-cookie import, disk cache or shared customer session is used. Requests remain source-bound and bounded, credentials are stripped, and protection responses return no catalog data even when their HTTP status is 200.

Live `/garage/add` with this server-issued CSRF and the observed E400 selection body still returns the Akamai challenge. Responses now expose `provider_error: browser_verification_required`, independently of application/stock evidence. `fresh-csrf-http.json` and `native-session-csrf-http.json` reproduce this result without retaining tokens or identifiers.

Passive browser observation shows separate Akamai script requests and an SDK telemetry POST in the successful browser page lifecycle; downloaded public scripts include the handler for `cpr_chlge` and browser DOM/XHR integration. This identifies a required verification layer, not a reproduced backend verification solution. Script digests and bounded inspection metadata are in `verification-script-inspection.json`; no challenge payload/token is replayed by production. The official Pro/mobile alternative requires an account and does not satisfy the anonymous requirement (`official-pro-entry-findings.json`). Full pure HTTP replacement-list discovery and native vehicle fitment remain unresolved.

### 2026-10-11: generic O'Reilly protocol validation

Live `POST /checkfit/products` in the established anonymous Brave session returned
`COMPATIBLE` for Dorman drain plug `DOR-090-164` and K&N filter `KAN-HP7040`, and
`INCOMPATIBLE` for `WIX-57060`, in one batch. This is a common product protocol,
not a filter-specific manufacturer lookup. Safe evidence:
`artifacts/oreilly-research/generic-multicategory-browser-http.json`.

`gaswise/providers/parts/oreilly_checkfit.py` implements the common request with exact
LCIN matching and uncertain universal/unknown flags. The caller must verify the
selected vehicle in the same session. It is not enabled as native route evidence
until independent HTTP vehicle-session bootstrap succeeds. Focused tests: 10 passed.

The user-supplied garage/add cURL was parsed as data, including ANSI Unicode
cookie escapes, and replayed using curl-cffi and system curl. Both returned 403
Access Denied; HTTP checkfit also returned 403. No cookie or CSRF values were
persisted in code or evidence. Browser success establishes multi-category native
behavior, not independent HTTP bootstrap. Manufacturer lookups remain supplemental.

### Sequential vehicle selection evidence

A fresh Brave capture confirms initial types/years/makes requests, makes reload
on year selection, years reload on make and model selection, then models,
submodels and engines. Lookup `year` is numeric, make/model IDs are strings,
and the engines payload uses `subModelId`. See
`artifacts/oreilly-research/vehicle-selection-browser-sequence.json`.

Replaying those exact observed lookup payloads, in order, in one fresh anonymous
HTTP session returned JSON for types, models, submodels and engines. Years and
makes still required browser verification, as did garage/add after the complete
lookup sequence. See `artifacts/oreilly-research/sequential-vehicle-http.json`.
Thus endpoint protection is selective; correct lookup ordering alone has not
established an independently usable selected-vehicle session. No production
native-fitment success is inferred from these lookup successes.

### Independent HTTP breakthrough: public vehicle configuration cookies

Three controlled fresh-session probes (baseline, header/garage bootstrap, and
observed browser headers plus bootstrap) did not clear years/makes/garage-add
verification. Evidence: `artifacts/oreilly-research/session-controlled-probes.json`.

A different native path succeeded: set retailer public catalog configuration
cookies ECV and EGV to the observed format
`vehicleTypeId-baseVehicleId-submodelId-engineId`. This uses no copied browser
session or anti-bot cookies. In a fresh curl-cffi session, `/header/data` confirmed
the exact selected base vehicle, vehicle identifier, engine and vehicle type.
Then `/checkfit/products` returned COMPATIBLE for DOR-090-164 and KAN-HP7040, and
INCOMPATIBLE for WIX-57060. Two additional fresh sessions reproduced all three.
Evidence: `artifacts/oreilly-research/public-vehicle-cookie-http.json`.

`OReillyHTTPSession.select_vehicle` implements numeric ID validation, ephemeral
configuration cookies and exact server selection confirmation. It never marks
selection verified merely because a cookie was set. Focused regression: 43 passed.

Scope: independent native HTTP vehicle selection and multi-category fitment now
work for verified retailer configuration IDs. Automatic VIN/plate-to-retailer-ID
discovery and wiring this path into `/v1/parts/fitment` remain separate unfinished
work. The implementation contains no E400 ID database and does not infer mappings
between AutoZone and O'Reilly IDs. The protected garage/add endpoint itself still
fails; this successful route does not call it.

### Combined retailer result and usage gate

When retailer lookups are enabled, every identified product assessment queries
both AutoZone and O'Reilly concurrently. A failed retailer returns an unavailable
evidence record instead of discarding the other retailer's result. The combined
`cross_check.source_statuses` reports both sources, including not_queried when a
lookup was not performed. Exact target-product evidence drives the decision;
store-brand alternatives do not vote against the requested product.

The response now includes `usage_decision` and `fitment_confirmed`:
- `verified_fit`: the final assessment confirms compatibility.
- `do_not_use`: explicitly incompatible.
- `verification_required`: unresolved or conflicting; do not recommend installation.

Only verified_fit sets fitment_confirmed=true. Unknown records remain distinct
from explicit incompatibility. One exact verified fit may support the product
when another retailer has no record; two explicit opposing results remain a
conflict. Supplier count alone is not a fitment requirement.

These contract/merger improvements do not finish O'Reilly automatic VIN/plate ID
discovery or unblock its generic product search. Focused parts/session tests: 64 passed.

### Integrated native VIN configuration lookup

O'Reilly `GET /vehicle/vin/{vin}` succeeded in a fresh anonymous HTTP session.
`OReillyHTTPSession.vin_configuration` validates vinIsValid, a unique response,
exact decoded year/make/model and numeric retailer configuration IDs. It retains
submodel/engine options rather than choosing one silently. Returned metadata and
evidence contain no VIN. PartsProvider now passes the resolved VIN to OReillyParts,
so the same path works after AutoZone plate-to-VIN resolution.

Live evidence: `artifacts/oreilly-research/native-vin-http-integrated.json`.
The production endpoint returned 200 for the original MANN case, with AutoZone
verified fit and O'Reilly unavailable; the latter must not be counted as verified.
Focused regressions: 69 passed.

Remaining blockers: native VIN response supplies make/model/submodel/engine IDs,
but no baseVehicleId; it cannot directly drive public vehicle-selection cookies.
Garage/add still requires browser verification even with a valid selected-car
cookie, and empty/placeholder vehicle cookies did not unlock it. Generic search,
type-ahead and cross-reference HTML remain protected. Anonymous public search
engine discovery probes produced no valid retailer URL and were not integrated.
No external browser/proxy is represented as direct pure HTTP success. Therefore
VIN configuration lookup is implemented, but fully automatic O'Reilly fitment
and arbitrary product discovery remain incomplete.

### Complete-name/category discovery and explicit reference evaluation

AutoZone and O'Reilly now search bounded queries from observed Amazon identifiers,
brand, full title and category. Exact brand/part identity remains mandatory for a
direct match. O'Reilly follows actual same-origin category links (up to three
pages), strips tracking queries from observed product links, then falls back to
its interchange index. A category match or fuzzy search result alone is never
fitment evidence.

AutoZone shelf records with an explicit `oemPartNumber` equal to the requested
part can establish a reference candidate only in the matching part category.
The reference number's manufacturer must also resolve uniquely to the Amazon
brand in O'Reilly's part-type/manufacturer index. At most three deduplicated
reference SKUs are checked through AutoZone's native VIN configuration protocol.
Only consistent complete native decisions become `verified_interchange` evidence;
unknown, conflicting or ambiguous manufacturer/reference data remains conditional.
Generic interchange candidates continue to be excluded from target-product votes.

Live endpoint validation (`artifacts/parts-discovery-live.json`):
- Bosch 6091C / B0864MTTRF: identified; AutoZone explicit OEM reference to STP
  CAF1904P and CAF1904M; O'Reilly manufacturer index confirms Bosch; both native
  reference checks reject the 2018 E400 configuration. Final incompatible /
  do_not_use, not a no-results inference.
- MANN HU7025Z / B019IPTB0W: identified; original AutoZone native fit remains
  compatible / verified_fit.

O'Reilly generic search/category documents remain browser-verification protected
in this environment; its fitment evidence reports unavailable. Its public
manufacturer/reference metadata still contributes to the combined lookup. These
results do not claim both retailers independently confirmed either application.
Focused parts tests: 85 passed; OpenAPI exported with verified_interchange relation.

### Public sitemap discovery instead of protected search documents

Live HTTP retesting with verified E400 vehicle cookies still received browser
verification for search, vehicle category and cross-reference documents. Switching
to a Safari transport profile did not resolve it. These attempts are recorded in
`artifacts/oreilly-research/selected-page-retest.json` and
`artifacts/oreilly-research/safari-selected-documents-http.json`.

A separate public discovery path works: robots.txt advertises sitemap.xml, which
lists 17 gzip URL documents. Anonymous HTTP read all 808,608 published URLs,
including 791,571 product URLs, without browser-cookie replay. No E400-specific
vehicle URL was present in those documents; they do not resolve baseVehicleId.

OReillyCatalog discovers exact part-number URLs, derives candidate retailer line
codes only from observed URLs, and verifies brand/part identity using native
pcp/compare-items JSON. It is wired into OReillyParts before category fallback;
verified JSON identity avoids loading the protected product document. Compressed
URL documents are cached in memory for one hour, with download, expansion,
map-count and candidate limits. This is an automatically refreshed URL cache,
not a manually maintained vehicle/fitment database.

Live validation: HP7040 resolves uniquely to KAN (rejecting the same-number
Standard Ignition product), 57060 resolves uniquely to WIX (rejecting other
same-number brands), and Bosch 6091C has no exact indexed product. Evidence:
`artifacts/oreilly-research/catalog-index-live.json` and
`artifacts/oreilly-research/sitemap-discovery-http.json`.

Scope: published direct-product discovery now has a pure HTTP alternative to the
blocked search/category pages. Sitemap absence is not incompatibility and is not
a complete retailer-inventory guarantee. Protected cross-reference documents and
compatible-makes/models still need verification; automatic VIN-to-baseVehicleId
remains unresolved. Do not describe this discovery success as independent native
O'Reilly fitment success for all vehicles.

### Native HTTP search investigation (2026-10-11)

A fresh Brave network observation of the E400 cabin-filter search showed the
`/search/v/a/144122/...` request redirecting to the cabin-filter category document.
The document response itself contained product identifiers including WP10110;
no separate product-list XHR was observed during this action. The shipped common
JavaScript calls `/es/product-autocomplete/v1/autocomplete` with `X-Client: OST`
and an API key published in the anonymous homepage config, falling back to
`/type-ahead/search`. `/header/search` is POST, not GET.

`OReillyHTTPSession.search_suggestions` now obtains the public search key from its
own anonymous homepage response, sends it only to the exact observed type-ahead
endpoint, validates at most eight suggestion terms, and clears the key on exit.
The integrated live request returned eight terms for cabin air filter without
browser cookies or account login. These are search suggestions, not product
inventory, vehicle compatibility, or negative-fitment evidence. The market ID
is caller-supplied; the observed value 25 is not a global default.

Anonymous native search documents, the legacy type-ahead fallback, and correctly
formatted header-search POST remain protected in this investigation. Full native
HTTP search is not complete. Evidence: `artifacts/oreilly-research/native-search-suggestions-integrated.json`
and `native-search-observed-http.json` / `native-search-fallback-http.json` in the
same directory. No private session values or public search key values are retained.

## Vehicle-scoped keyword search

`POST /v1/parts/search` accepts a keyword, exactly one VIN or US state/plate identity, and `max_results` from 1 to 6. It obtains the decoded vehicle configuration, searches AutoZone's vehicle-scoped catalog, and checks each exact product candidate with native fitment evidence. Search relevance alone does not establish compatibility. Conditional, blocked or mismatched evidence returns `needs_confirmation`; unavailable searches return no invented products.

The 2026-10-11 local live validation checked six oil-filter candidates and verified three fits, with three requiring confirmation. This is run-specific evidence, not a promise of future source availability. The frontend has separate keyword-search and Amazon-link verification modes; identifiers remain in session memory.
