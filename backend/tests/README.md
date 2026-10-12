# Test organization

Tests are grouped by business area and upstream source. Run from `backend/` with `uv run pytest tests/<area> -q`; use `uv run pytest -q` for the complete suite.

- `app/`: lifecycle, dependency injection, authentication boundaries and package dependencies.
- `pricing/`: cost ranking, comparison, octane matching, fuel estimates and smart search.
- `vehicles/`: catalog selection, VIN/plate resolution and fuel specifications.
- `parts/`: product fitment, manufacturer evidence and interchange behavior.
- `providers/`: source-specific behavior, grouped into GasBuddy, Google, Waze and generic pricing.
- `support/`: shared fake providers, records, response builders and repository paths. Support modules contain no test cases.
- `fixtures/`: offline captured responses. Import `FIXTURES` from `tests.support.paths`; avoid paths relative to individual test locations.

`conftest.py` isolates local configuration so tests cannot accidentally pick up live provider credentials. Shared code imports `tests.support.<area>` rather than another `test_*.py` module. Package boundary checks prevent core/provider layers from importing higher-level orchestration or HTTP wiring.
