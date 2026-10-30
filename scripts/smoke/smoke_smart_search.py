"""One explicit search; output only diagnostic counts, never credentials or price history.

Run with `uv run python ../scripts/smoke/smoke_smart_search.py` from backend.
No polling, automatic retry, Cloud configuration change, or paid Places fallback
when an authorized Maps website session is configured.
"""

import argparse
import asyncio
import json
from collections import Counter

import httpx

from gaswise.domain.pricing.comparison import ineligible
from gaswise.main import create_app
from gaswise.contracts.smart import SmartResult
from gaswise.app.settings import Settings


async def run(args):
    settings = Settings()
    if settings.mode == "demo":
        raise SystemExit("Live smoke requires a configured live mode.")
    if args.routes and not (settings.maps_web_routes_enabled or (
        settings.mode == "google" and settings.google_routes_enabled
    )):
        raise SystemExit("Real routing is not configured; no provider calls were made.")
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://smoke") as client:
            response = await client.post("/v1/smart/search", headers={
                "Authorization": "Bearer " + settings.api_token.get_secret_value(),
            }, json={
                "origin": {"lat": args.lat, "lng": args.lng},
                "radius_meters": args.radius, "fuel_type": args.fuel_type,
                "payment_type": args.payment, "calculate_routes": args.routes,
                "route_limit": 2, "maps_detail_limit": args.maps_detail_limit,
                "trip_mode": args.trip_mode,
                **({"destination": {"lat": args.destination_lat, "lng": args.destination_lng}}
                   if args.trip_mode == "on_route" else {}),
            })
            if response.status_code != 200:
                print(json.dumps({"http_status": response.status_code, "detail": response.json().get("detail")}))
                return 1
            result = response.json()
            result.pop("coverage", None)
            parsed = SmartResult.model_validate(result)
            snapshot = parsed.snapshot
            exclusions = Counter(ineligible(s, snapshot.query, snapshot.collected_at) or "eligible"
                                 for s in snapshot.stations)
            if args.diagnose_matches:
                # Public station identities only; omit fuel prices and all session data.
                print(json.dumps({
                    "unmatched_addresses": [q.address for q in snapshot.unlocated_gasbuddy],
                    "inventory_addresses": [s.address for s in snapshot.inventory],
                }, indent=2))
            print(json.dumps({
                "http_status": response.status_code,
                "source_statuses": [s.model_dump() for s in snapshot.source_statuses],
                "upstream_calls": parsed.upstream_calls,
                "located_quotes": len(snapshot.stations),
                "unique_station_keys": len({s.canonical_id or f"{s.source}:{s.id}" for s in snapshot.stations}),
                "unlocated_gasbuddy_quotes": len(snapshot.unlocated_gasbuddy),
                "eligibility_counts": dict(exclusions),
                "routed_candidates": len(snapshot.routes),
                "ranking_available": parsed.ranking is not None,
                "ranked_candidates": len(parsed.ranking.results) if parsed.ranking else 0,
                "route_sources": sorted({r.route.source for r in snapshot.routes}),
                "baseline_distance_meters": snapshot.baseline.distance_meters if snapshot.baseline else None,
                "cost_model": "fixed_purchase_plus_extra_road_miles_divided_by_user_mpg",
                "candidate_costs": [{
                    "station_name": row.station.name,
                    "road_distance_meters": row.route.distance_meters,
                    "route_duration_seconds": row.route.duration_seconds,
                    "duration_basis": row.route.duration_basis,
                    "detour_miles": str(row.detour_miles),
                    "detour_fuel_gallons": str(row.detour_fuel_gallons),
                    "mpg_used": str(row.mpg_used),
                    "actual_fuel_cost": str(row.actual_fuel_cost),
                } for row in parsed.ranking.results] if parsed.ranking else [],
                "price_history_saved": False,
            }, indent=2))
            return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, default=34.03938)
    parser.add_argument("--lng", type=float, default=-118.2663)
    parser.add_argument("--radius", type=float, default=5000)
    parser.add_argument("--fuel-type", choices=["regular", "midgrade", "premium", "diesel"], default="premium")
    parser.add_argument("--payment", choices=["cash", "credit"], default="credit")
    parser.add_argument("--maps-detail-limit", type=int, choices=range(6), default=1)
    parser.add_argument("--routes", action="store_true")
    parser.add_argument("--trip-mode", choices=["round_trip", "on_route"], default="round_trip")
    parser.add_argument("--destination-lat", type=float, default=34.0522)
    parser.add_argument("--destination-lng", type=float, default=-118.2437)
    parser.add_argument("--diagnose-matches", action="store_true")
    raise SystemExit(asyncio.run(run(parser.parse_args())))
