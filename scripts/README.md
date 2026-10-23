# GasWise scripts

Scripts are organized by purpose. Run the commands below from `backend/` with `uv run python ../scripts/...` so they use the backend dependencies and local configuration. The standalone Waze HTTP/Android helpers can also run with `python3` from the repository root.

| Folder | Purpose |
| --- | --- |
| `tooling/` | Local development and contract generation |
| `smoke/` | End-to-end service/provider validation |
| `diagnostics/gasbuddy/` | GasBuddy transport/session investigation |
| `diagnostics/waze/` | Waze HTTP, browser and Android diagnostics |
| `research/amazon/` | Public product identity probes |
| `research/autozone/` | Public product search and native fitment probes |
| `research/edmunds/` | Public specification HTTP/XHR probes |

## Tooling

`tooling/export_openapi.py` exports `contracts/openapi.json` locally without calling providers:

```sh
uv run python ../scripts/tooling/export_openapi.py
```

## Smoke checks

| Script | What it checks | Requirements |
| --- | --- | --- |
| `smoke/check_live_gasbuddy.py` | Quotes through the running GasWise API | Running service, configured source; makes live calls |
| `smoke/check_no_browser_runtime.py` | Cold-start GasBuddy HTTP path with Playwright imports blocked | Configured source; makes live calls |
| `smoke/smoke_smart_search.py` | Smart discovery and optional routes | Local configuration; makes live calls and may use paid providers |
| `smoke/smoke_public_specifications.py` | Public vehicle fuel specification evidence | Network; makes live calls |

```sh
uv run python ../scripts/smoke/check_live_gasbuddy.py --repeat 3
uv run python ../scripts/smoke/smoke_smart_search.py --help
uv run python ../scripts/smoke/smoke_public_specifications.py --help
```

## Source diagnostics

| Script | Purpose / requirements |
| --- | --- |
| `diagnostics/gasbuddy/probe_gasbuddy_browserless.py` | Compare clean HTTP transports; network and curl |
| `diagnostics/source_reachability.py` | Matched local/server AAA and GasBuddy probes; safe response metadata only |
| `diagnostics/egress_lanes.py` | Prove each pricing egress lane with an HTTPS 200 and a US location; proxy credentials are redacted |
| `diagnostics/pricing_baseline.py` | Repeat the browser's Smart search request and report latency, per-source quote counts, coverage and upstream calls |
| `diagnostics/gasbuddy/probe_gasbuddy_session.py` | Compare browser loading and session HTTP; Playwright and Chrome |
| `diagnostics/waze/check_waze_browser.py` | Browser endpoint probe; Playwright and Chrome |
| `diagnostics/waze/check_waze_fuel.py` | HTTP fuel endpoint/session probe; network |
| `diagnostics/waze/query_waze_http.py` | HTTP station query; optional local login/session configuration |
| `diagnostics/waze/read_waze_android.py` | Read current station screen; ADB and an Android device/emulator |

Browser diagnostics use the optional browser dependencies. They are independent of production provider selection.

```sh
uv run python ../scripts/diagnostics/waze/check_waze_browser.py --headful
python3 ../scripts/diagnostics/waze/query_waze_http.py --help
python3 ../scripts/diagnostics/waze/read_waze_android.py --help
```

## Research probes

| Script | Purpose |
| --- | --- |
| `research/amazon/public_product_probe.py` | Selected Amazon product identity; curl-cffi and BeautifulSoup |
| `research/autozone/public_search_fitment_probe.py` | Public product candidates and vehicle application hierarchy; curl-cffi |
| `research/autozone/native_check_fit_probe.py` | Native fitment; curl-cffi and explicitly supplied test VIN or plate/state |
| `research/edmunds/clean_http_probe.py` | Compare public HTTP transport results; HTTPX and curl |
| `research/edmunds/public_xhr_probe.py` | Public metadata and specification JSON; curl-cffi |

These probes make live upstream calls. Amazon and Edmunds output files remain in `artifacts/amazon-research/` and `artifacts/edmunds-research/`. AutoZone probes print results. Captured upstream assets and evidence stay in `artifacts/`; reusable executable scripts live here.

```sh
uv run --with beautifulsoup4 python ../scripts/research/amazon/public_product_probe.py
uv run python ../scripts/research/edmunds/clean_http_probe.py
```

## Adding a script

Choose the appropriate purpose and provider folder. Document the command, dependencies, upstream calls and output location in this index. Resolve repository/output paths from `__file__` when needed, and write research evidence to `artifacts/` rather than beside script source. Keep automated offline regression tests under `backend/tests/`.
