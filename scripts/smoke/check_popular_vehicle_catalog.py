"""Validate the market fixture against the live EPA/DOE catalog and GasWise resolver.

Run from backend:
    uv run python ../scripts/smoke/check_popular_vehicle_catalog.py

This diagnostic deliberately answers configuration questions by trying catalog
choices until it finds one supported liquid-fuel record. The product resolver
continues to ask the human instead of silently making those choices.
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from gaswise.app.settings import Settings
from gaswise.contracts.vehicles import VehicleResolveRequest
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.services.vehicles.selection import VehicleSelector, compact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "backend/tests/fixtures/us_popular_vehicles_2025.json"


def belongs_to_case(model, expected_prefixes):
    normalized = compact(model)
    return any(normalized.startswith(compact(prefix)) for prefix in expected_prefixes)


def assert_safe_candidates(case, result):
    visible = [*result.matched_models, *(choice.value for choice in result.choices)]
    for forbidden in case.get("must_not_match", []):
        if any(compact(forbidden) in compact(value) for value in visible):
            raise AssertionError(f"off-family candidate {forbidden!r}: {visible}")


async def find_supported(selector, case, request, depth=0):
    if depth > 8:
        return None, "question_depth_exceeded"
    result = await selector.resolve(request)
    assert_safe_candidates(case, result)
    if result.status == "resolved":
        return result, None
    if result.status == "no_match":
        return None, result.question or "no_match"

    field = result.answer_field
    if field not in {"model", "catalog_model", "option_vehicle_id", "body_style", "drivetrain"}:
        return None, f"unexpected_question:{field}"
    reasons = []
    for choice in result.choices:
        update = {field: int(choice.value) if field == "option_vehicle_id" else choice.value}
        if field == "model":
            update.update({"catalog_model": None, "option_vehicle_id": None})
        next_request = result.selection.model_copy(update=update)
        resolved, reason = await find_supported(selector, case, next_request, depth + 1)
        if resolved is not None:
            return resolved, None
        reasons.append(reason)
    return None, ";".join(dict.fromkeys(filter(None, reasons))) or "no_choices"


async def run(args):
    fixture = json.loads(Path(args.fixture).read_text())
    year = fixture["year"]
    rows = []
    store = None
    if args.persist:
        dsn = Settings().database_url.get_secret_value()
        if not dsn:
            raise SystemExit("--persist requires GASWISE_DATABASE_URL; no provider calls were made")
        store = await PostgresPricingCache.connect(dsn)
    try:
        async with httpx.AsyncClient(timeout=args.timeout) as client:
            selector = VehicleSelector(VehicleProvider(client, persistent_cache=store))
            for case in fixture["cases"]:
                request = VehicleResolveRequest(year=year, make=case["make"], model=case["query"])
                try:
                    result, reason = await find_supported(selector, case, request)
                    if result is None:
                        passed = bool(case.get("expected_unavailable"))
                        row = {
                            **case,
                            "status": "expected_unavailable" if passed else "failed",
                            "reason": reason,
                        }
                    else:
                        vehicle = result.vehicle
                        passed = (
                            not case.get("expected_unavailable")
                            and vehicle.year == year
                            and vehicle.make == case["make"]
                            and belongs_to_case(vehicle.model, case["expected_prefixes"])
                            and vehicle.source == "fueleconomy_gov"
                            and vehicle.combined_mpg > 0
                        )
                        row = {
                            **case,
                            "status": "passed" if passed else "failed",
                            "vehicle_id": vehicle.id,
                            "resolved_model": vehicle.model,
                            "fuel_type": vehicle.fuel_type,
                            "combined_mpg": str(vehicle.combined_mpg),
                        }
                except Exception as error:  # diagnostic boundary: retain case identity
                    passed = False
                    row = {**case, "status": "failed", "reason": f"{type(error).__name__}:{error}"}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    finally:
        if store is not None:
            await store.close()

    passed_count = sum(row["status"] in {"passed", "expected_unavailable"} for row in rows)
    summary = {
        "fixture_year": year,
        "total": len(rows),
        "passed": passed_count,
        "resolved": sum(row["status"] == "passed" for row in rows),
        "expected_unavailable": sum(row["status"] == "expected_unavailable" for row in rows),
        "failed": len(rows) - passed_count,
        "top10_cases": sum(row["group"] == "top10" for row in rows),
        "supplemental_cases": sum(row["group"] == "supplemental" for row in rows),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="write validated public EPA records to the configured PostgreSQL reference cache",
    )
    raise SystemExit(asyncio.run(run(parser.parse_args())))
