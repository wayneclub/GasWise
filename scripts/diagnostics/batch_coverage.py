"""Dry-run fixed-base coverage plans without making provider requests.

Run from ``backend/``::

    uv run python ../scripts/diagnostics/batch_coverage.py --json
    uv run python ../scripts/diagnostics/batch_coverage.py --strategy legacy --json
"""

import argparse
import asyncio
import json
import os

from gaswise.contracts.common import Point
from gaswise.domain.pricing.batch_coverage import requested_radii, simulated_area
from gaswise.domain.pricing.collection_bases import BASES
from gaswise.services.pricing.discovery import shared_viewport


def plan(strategy, base_radius, max_radius, cell_km):
    requested = requested_radii(
        list(BASES), strategy=strategy, base_radius=base_radius, max_radius=max_radius
    )
    effective = {}
    for base, radius in requested.items():
        point = Point(lat=BASES[base][0], lng=BASES[base][1])
        _, effective[base] = shared_viewport(point, radius)
    reserve_per_base = 9 + 9 + 4 + 3  # GasBuddy x2 (max_pages=8), Maps/Waze all-fuels.
    return {
        "strategy": strategy,
        "base_count": len(BASES),
        "jobs_per_cycle": len(BASES) * 4,
        "request_reserve_per_cycle": len(BASES) * reserve_per_base,
        "expanded_bases": [
            {"base": base, "requested_radius_meters": round(requested[base]),
             "effective_radius_meters": round(effective[base])}
            for base in sorted(BASES) if requested[base] > base_radius
        ],
        "radius_counts": {
            str(round(radius)): sum(round(value) == round(radius) for value in effective.values())
            for radius in sorted(set(effective.values()))
        },
        "area": simulated_area(effective, cell_km=cell_km),
    }


async def database_report(dsn, hours):
    """Read-only production/current-state aggregates; never loads raw payloads."""
    import asyncpg

    connection = await asyncpg.connect(dsn, timeout=10, command_timeout=30)
    try:
        async with connection.transaction(readonly=True):
            columns = set(await connection.fetch(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema='gaswise' AND table_name='collection_runs'"""
            ))
            columns = {row["column_name"] for row in columns}
            coverage_columns = {
                "canonical_count", "new_canonical_count", "located_count",
                "priced_count", "inventory_overlap_count",
            }
            extra = ",".join(
                f"sum({name})::bigint AS {name}" for name in sorted(coverage_columns)
            ) if coverage_columns <= columns else ",".join(
                f"NULL::bigint AS {name}" for name in sorted(coverage_columns)
            )
            runs = await connection.fetch(f"""
                SELECT source,base,fuel,count(*) AS attempts,
                       count(*) FILTER(WHERE outcome='success') AS successes,
                       sum(http_requests)::bigint AS http_requests,
                       sum(quote_count)::bigint AS raw_rows,
                       sum(station_count)::bigint AS provider_stations,{extra}
                FROM gaswise.collection_runs
                WHERE finished_at>=now()-$1*interval '1 hour'
                GROUP BY source,base,fuel ORDER BY source,base,fuel
            """, hours)
            stations = await connection.fetch("""
                SELECT source,count(*) AS provider_stations,
                       count(DISTINCT COALESCE(canonical_id,source||':'||station_id)) AS canonical_stations,
                       count(*) FILTER(WHERE metadata?'location') AS located,
                       count(DISTINCT canonical_id) FILTER(
                           WHERE canonical_id LIKE 'google_places:%') AS inventory_overlap
                FROM gaswise.stations GROUP BY source ORDER BY source
            """)
            history = await connection.fetch("""
                SELECT source,fuel_type,count(*) AS raw_rows,
                       count(DISTINCT station_id) AS provider_stations,
                       count(DISTINCT COALESCE(canonical_id,source||':'||station_id)) AS canonical_stations,
                       count(*) FILTER(WHERE price_per_gallon>0) AS valid_prices,
                       count(*) FILTER(WHERE attributes?'location') AS located
                FROM gaswise.quote_history GROUP BY source,fuel_type ORDER BY source,fuel_type
            """)
        return {
            "window_hours": hours,
            "exact_run_coverage_metrics": coverage_columns <= columns,
            "runs_by_source_base_fuel": [dict(row) for row in runs],
            "station_inventory": [dict(row) for row in stations],
            "history_by_source_fuel": [dict(row) for row in history],
        }
    finally:
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=("legacy", "isolated_radius_v1"),
                        default="isolated_radius_v1")
    parser.add_argument("--base-radius", type=int, default=10000)
    parser.add_argument("--max-radius", type=int, default=20000)
    parser.add_argument("--cycle-request-budget", type=int,
                        default=int(os.environ.get("GASWISE_BASE_COLLECTION_CYCLE_REQUEST_BUDGET", "2300")))
    parser.add_argument("--cell-km", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--database-url", default=os.environ.get("GASWISE_DATABASE_URL", ""),
                        help="Optional PostgreSQL DSN; read-only aggregates only. Prefer the environment variable.")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()
    result = plan(args.strategy, args.base_radius, args.max_radius, args.cell_km)
    result["rate_budget_guard"] = {
        "limit": args.cycle_request_budget,
        "planned": result["request_reserve_per_cycle"],
        "ok": result["request_reserve_per_cycle"] <= args.cycle_request_budget,
    }
    if not result["rate_budget_guard"]["ok"]:
        raise SystemExit("planned request reserve exceeds cycle request budget")
    if args.database_url:
        result["database"] = asyncio.run(database_report(args.database_url, args.hours))
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
