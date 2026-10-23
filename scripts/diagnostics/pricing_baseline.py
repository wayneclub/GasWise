"""Repeatable user-path baseline for Smart search price collection.

Measures the same request the browser sends: per-run wall time, server timings,
quote counts by source, coverage and upstream call counts. Use it before and
after a pricing change to compare like with like. Never prints the API token.

Run from ``backend/`` so the repository's backend dependencies are available::

    uv run python ../scripts/diagnostics/pricing_baseline.py --lat 34.05 --lng -118.24
    uv run python ../scripts/diagnostics/pricing_baseline.py --fuel premium --repeat 3 --json

The token comes from ``--token`` or ``GASWISE_API_TOKEN``. The base URL comes
from ``--base-url`` or ``GASWISE_BASE_URL`` (default ``http://127.0.0.1:8000``).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

import httpx

SOURCES = ("google_maps_web", "gasbuddy_web", "waze", "google_places")


def body(args) -> dict:
    pages = args.pages
    if pages is None:
        # Mirrors frontend searchBody: Maps summaries only publish Regular.
        pages = 3 if args.fuel == "regular" else 5
    return {
        "origin": {"lat": args.lat, "lng": args.lng},
        "radius_meters": args.radius_miles * 1609.344,
        "max_results": 100,
        "fuel_type": args.fuel,
        "payment_type": "cash_or_credit",
        "strategy": "best_value",
        "opening_policy": "require_open",
        "calculate_routes": not args.no_routes,
        "route_limit": args.route_limit,
        "estimate_unrouted_routes": not args.no_routes,
        "discovery_tiles": args.discovery_tiles,
        "gasbuddy_page_limit": pages,
        "station_lookup_limit": 5,
        "maps_detail_limit": args.detail_limit,
        "force_refresh": args.force,
    }


def percentile(values: list[float], fraction: float):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return round(ordered[index], 1)


def summarize(run: dict) -> dict:
    payload = run.get("result") or {}
    snapshot = payload.get("snapshot") or {}
    coverage = payload.get("coverage") or {}
    statuses = {row.get("source"): row for row in snapshot.get("source_statuses") or []}
    stations = snapshot.get("stations") or []
    counts = {source: sum(station.get("source") == source for station in stations) for source in SOURCES}
    timings = payload.get("timings_ms") or {}
    return {
        "ok": run["ok"],
        "error": run.get("error"),
        "wall_ms": run["wall_ms"],
        "server_ms": timings.get("total"),
        "timings_ms": timings,
        "stations": len(stations),
        "stations_by_source": counts,
        "eligible": coverage.get("eligible"),
        "displayed": coverage.get("displayed"),
        "discovered": coverage.get("discovered"),
        "priced": coverage.get("priced"),
        "discovery_area_covered": snapshot.get("discovery_area_covered"),
        "source_statuses": {
            name: {"status": row.get("status"), "quotes": row.get("quote_count"), "detail": row.get("detail")}
            for name, row in statuses.items()
        },
        "upstream_calls": payload.get("upstream_calls") or {},
        "cache_hits": payload.get("cache_hits"),
        "warnings": len(snapshot.get("warnings") or []),
    }


def execute(client: httpx.Client, args) -> dict:
    started = time.perf_counter()
    try:
        response = client.post("/v1/smart/search", json=body(args))
    except httpx.HTTPError as error:
        return {"ok": False, "wall_ms": round((time.perf_counter() - started) * 1000, 1),
                "error": type(error).__name__, "result": None}
    wall = round((time.perf_counter() - started) * 1000, 1)
    if response.status_code != 200:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        return {"ok": False, "wall_ms": wall, "error": {"status": response.status_code, "detail": detail},
                "result": None}
    return {"ok": True, "wall_ms": wall, "error": None, "result": response.json()}


def report(runs: list[dict]) -> dict:
    rows = [summarize(run) for run in runs]
    successful = [row for row in rows if row["ok"]]
    walls = [row["wall_ms"] for row in successful]
    totals = [row["server_ms"] for row in successful if row["server_ms"] is not None]
    return {
        "runs": rows,
        "summary": {
            "attempts": len(rows),
            "success_rate": round(len(successful) / len(rows), 3) if rows else None,
            "wall_ms": {"p50": percentile(walls, 0.5), "p95": percentile(walls, 0.95),
                        "min": min(walls) if walls else None, "max": max(walls) if walls else None},
            "server_ms": {"p50": percentile(totals, 0.5), "p95": percentile(totals, 0.95)} if totals else None,
            "mean_stations_by_source": {
                source: round(statistics.fmean(row["stations_by_source"][source] for row in successful), 1)
                if successful else None
                for source in SOURCES
            },
            "mean_eligible": round(statistics.fmean(row["eligible"] for row in successful), 1)
            if successful and all(row["eligible"] is not None for row in successful) else None,
            "mean_displayed": round(statistics.fmean(row["displayed"] for row in successful), 1)
            if successful and all(row["displayed"] is not None for row in successful) else None,
        },
    }


def line(index: int, row: dict) -> str:
    if not row["ok"]:
        return f"run {index:<2} FAILED {row['error']}"
    counts = " ".join(f"{name}={count}" for name, count in row["stations_by_source"].items() if count)
    parts = [
        f"run {index:<2}",
        f"wall={row['wall_ms']:.0f}ms",
        f"server={row['server_ms']:.0f}ms" if row["server_ms"] is not None else "server=?",
        f"stations={row['stations']} ({counts or 'none'})",
        f"eligible={row['eligible']}",
        f"displayed={row['displayed']}",
    ]
    covered = row["discovery_area_covered"]
    if covered is not None:
        parts.append(f"area={covered:.0%}")
    timings = row["timings_ms"]
    if timings.get("discovery") is not None:
        parts.append(f"discovery={timings['discovery']:.0f}ms")
    if timings.get("routes_and_averages") is not None:
        parts.append(f"routes={timings['routes_and_averages']:.0f}ms")
    return "  ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("GASWISE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("GASWISE_API_TOKEN", ""),
                        help="Bearer token. Prefer GASWISE_API_TOKEN so it never lands in shell history.")
    parser.add_argument("--lat", type=float, default=34.05)
    parser.add_argument("--lng", type=float, default=-118.24)
    parser.add_argument("--fuel", default="regular", choices=["regular", "midgrade", "premium", "diesel"])
    parser.add_argument("--radius-miles", type=float, default=5)
    parser.add_argument("--pages", type=int, default=None, help="GasBuddy page limit; defaults like the frontend.")
    parser.add_argument("--discovery-tiles", type=int, default=20)
    parser.add_argument("--detail-limit", type=int, default=5)
    parser.add_argument("--route-limit", type=int, default=20)
    parser.add_argument("--no-routes", action="store_true")
    parser.add_argument("--force", action="store_true", help="Bypass the shared freshness window where allowed.")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180, help="HTTP timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit the summary as JSON.")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    runs = []
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=args.timeout) as client:
        for _ in range(max(1, args.repeat)):
            runs.append(execute(client, args))
    result = report(runs)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for index, row in enumerate(result["runs"], 1):
            print(line(index, row))
        print(json.dumps(result["summary"], indent=2))
    return 0 if all(row["ok"] for row in result["runs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
