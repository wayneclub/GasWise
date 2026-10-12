# Python package structure and extension

GasWise organizes Python source by responsibility, then by domain or upstream source. The package root contains only `main.py` and `__init__.py`. `gaswise.main:app` remains the deployment entry point.

```text
backend/
├── gaswise/
│   ├── main.py
│   ├── app/                    # Settings, dependency container, composition/lifecycle
│   ├── api/                    # HTTP routes, auth and execution policy
│   ├── contracts/              # Common, pricing, smart, vehicles and parts schemas
│   ├── domain/
│   │   ├── ports.py            # Provider capabilities and errors
│   │   ├── pricing/            # Comparison, identity, fuel costs and grade policy
│   │   ├── vehicles/           # Fuel requirements, specification policy and matching
│   │   └── validation/         # Pure shared URL validation
│   ├── services/
│   │   ├── pricing/            # Collection, recommendations and smart workflows
│   │   ├── vehicles/           # Vehicle/VIN/plate selection and fuel assessment
│   │   └── parts/              # Product identification and fitment workflow
│   └── providers/
│       ├── pricing/            # Registry, aggregation, generic feeds, demo and AAA
│       ├── gasbuddy/           # Feed/web adapters, sessions, optional browser, brands
│       ├── google/             # Places, Maps website prices and routes
│       ├── waze/               # Provider, venue details and protocol
│       ├── vehicles/           # EPA, NHTSA, plate lookup, specifications and Hertz
│       ├── parts/              # Retailer/manufacturer/product protocol adapters
│       └── http/               # Shared anonymous and session HTTP transports
└── tests/
    ├── app/                    # Runtime ownership and package boundary tests
    ├── pricing/                # Ranking, comparison, fuel, identity and smart flow
    ├── vehicles/               # Vehicle/VIN/plate/fuel/specification behavior
    ├── parts/                  # Fitment, interchange and manufacturer behavior
    ├── providers/              # Source-specific tests, grouped by source
    ├── support/                # Shared fake providers, records and path helpers
    ├── fixtures/               # Captured offline input data
    └── conftest.py             # Isolate local/live environment configuration
```

Executable diagnostics and research scripts are separately organized under `scripts/`; see the [script index](../scripts/README.md). Captured research outputs and upstream assets remain under `artifacts/`.

## Dependency direction

`app/bootstrap.py` constructs concrete providers and services and owns their lifetime. `api/` receives dependencies through FastAPI's `Depends` and invokes application operations. `services/` coordinates workflows; `domain/` owns rules and capabilities. Providers translate upstream protocols into contracts and can reuse domain rules. Contracts depend on other contracts and pure validation.

Core rules and contracts must not import app wiring, HTTP routes, services or providers. Providers must not import services or app wiring. Services must not import app wiring or HTTP routes. Architecture tests enforce these boundaries, including imports inside functions. A shared drivetrain matching rule moved into `domain/vehicles/matching.py` so specification adapters no longer depend on the VIN service.

Choose a module's location based on its responsibility. Domain rules belong under `domain/<domain>/`; orchestration under `services/<domain>/`; remote parsing/requests under `providers/<source>/`. Tests belong in the corresponding area, and reusable test data/fakes belong in `tests/support/`. Do not import helpers from other test cases.

## Contracts and imports

Import contracts directly from their domain, for example:

```python
from gaswise.contracts.common import Point, Station
from gaswise.contracts.search import RankOptions, Search
from gaswise.contracts.vehicles import VehicleProfile
from gaswise.domain.ports import PriceSnapshot, ProviderError
```

The former flat `gaswise.models`, `gaswise.settings`, `gaswise.service`, `gaswise.smart` and flat provider paths have been removed. Repository source, diagnostics, tests and patch targets use the classified paths. Python consumers importing those former internal modules must update their imports. Public HTTP paths, request/response schemas, authentication, status codes and SSE events remain compatible.

`Search` and smart reranking share `RankOptions`; payment, membership, octane, freshness, strategy and purchase parameters have one definition.

## Add or replace a dependency

For a normalized HTTPS feed, configure `GASWISE_PRICE_SOURCES`. For a new protocol, implement the capability in `domain/ports.py`, put the adapter in the relevant provider folder, and register it in `app/bootstrap.py`:

```python
registry.register("new_source", adapter, timeout_seconds=15)
```

Every station must identify the registered source. Collection retains per-source deadlines, provenance checks and failure isolation. An all-source failure raises an explicit error. Registration integrates normalized collection and recommendations; smart inventory matching remains an explicit workflow with upstream-call accounting. A new smart acquisition strategy needs a workflow change or a replacement smart service. Routing selection remains independent of price registration.

Existing `create_app(..., provider=..., vehicle_provider=..., vin_provider=..., plate_provider=...)` injection arguments continue to work. An alternate runtime can pass `service_factory`, an async context manager accepting `(Settings, ProviderOverrides)` and yielding `Services`. It owns its resources and cleanup.

Request dependencies can use FastAPI overrides:

```python
from gaswise.api.dependencies import get_services

app.dependency_overrides[get_services] = lambda: fixture_services
```

Settings and container definitions are in `gaswise.app.settings` and `gaswise.app.runtime`. State remains at `app.state.services`, `app.state.settings` and `app.state.operations`. Construction patch targets are in `gaswise.app.bootstrap`; SSE sleeping is in `gaswise.api.recommendations`.

## Lifetime and operation policy

The composition root uses `AsyncExitStack` for both HTTP clients and registers cleanup immediately after construction. It closes in-flight smart tasks, then the price worker, then clients. Partial-startup failure also releases acquired resources.

One `api.operations.OperationRunner` is shared per app. Saturation returns 429 with `Retry-After`; provider failures return 502 and deadlines return 504. Success, errors, cancellation and deadlines return capacity. Smart reranking retains its 409/422 mapping and makes no acquisition calls. SSE validates the first snapshot before returning 200 and acquires capacity only during each search.

`providers/http/httpx_public.py` shares bounded anonymous reads between specifications and parts. It removes inherited authentication headers, disables redirects and always closes responses. Curl transport and authenticated Maps/Waze policies remain separately selectable.

## Verification

Run from `backend`:

```sh
uv run pytest -q
uv run pytest tests/vehicles -q
uv run pytest tests/providers/gasbuddy -q
uv run ruff check gaswise tests
uv run python ../scripts/tooling/export_openapi.py
```

Source and test relocation preserved all 468 existing tests. Five package-boundary/import checks were added, bringing the suite to 473 passing tests. Ruff and formatting checks pass. The exported OpenAPI contract is unchanged. A built wheel also passes cold startup, health, synthetic recommendations and source discovery with browser imports blocked. Verification uses mocked or synthetic providers and makes no live or paid provider calls.

The generic Git ignore rule for `parts/` is now anchored to `/parts/`, so classified parts source and tests are included in version control and wheel packaging.
