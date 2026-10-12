import asyncio
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from gaswise.contracts.common import Route
from gaswise.contracts.search import (
    BreakEven,
    Decision,
    PriceComparison,
    RankedStation,
    Search,
    SearchResult,
    StrategyRecommendation,
    TopTierPreference,
)
from gaswise.domain.ports import Provider, ProviderError
from gaswise.domain.pricing.comparison import (
    cashback_rate,
    comparable_prices,
    comparison_price,
    net_purchase_price,
    select_prices,
)
from gaswise.domain.pricing.fuel import fuel_model, route_fuel
from gaswise.domain.pricing.top_tier import tag_top_tier
from gaswise.domain.vehicles.fuel_policy import check_vehicle_fuel, resolve_fuel_query
from gaswise.services.pricing.collection import collect_prices


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SearchService:
    def __init__(self, provider: Provider, mode: str, vehicles=None, vehicle_profile=None, top_tier=None):
        self.provider, self.mode = provider, mode
        self.vehicles, self.vehicle_profile = vehicles, vehicle_profile
        self.top_tier = top_tier

    async def search(self, query: Search) -> SearchResult:
        vehicle = self.vehicle_profile
        if query.vehicle_id is not None:
            if vehicle is None:
                if self.vehicles is None:
                    raise ProviderError("vehicle_catalog_not_configured")
                vehicle = await self.vehicles.vehicle(query.vehicle_id)
            if vehicle.id != query.vehicle_id:
                raise ProviderError("vehicle_id_mismatch")
        query = resolve_fuel_query(query, vehicle)
        if vehicle is not None:
            check_vehicle_fuel(vehicle, query)
        destination = query.destination if query.trip_mode == "on_route" else query.origin
        baseline = (
            await self.provider.route(query.origin, destination)
            if query.trip_mode == "on_route"
            else Route(distance_meters=0, duration_seconds=0, source="no_trip")
        )
        snapshot = await collect_prices(self.provider, query)
        stations, statuses = snapshot.stations, snapshot.statuses
        if self.top_tier is not None:
            stations = tag_top_tier(stations, self.top_tier.index)
        now = datetime.now(UTC)
        selections, excluded, warnings = select_prices(stations, query, now)
        if vehicle and vehicle.fuel_recommendation:
            warnings.extend(vehicle.fuel_recommendation.assessment_warnings)
        warnings.append(
            "Costs assume fixed purchased gallons and station price for detour fuel; exclude tolls, queues and vehicle wear."
        )
        warnings.append(
            "Source agreement is a rule-based signal, not measured accuracy or proof of independent data feeds."
        )
        if query.allow_unknown_payment:
            warnings.append(
                "Unknown payment conditions were explicitly allowed; confirm the payable price before a detour."
            )
        for status in statuses:
            if status.status != "ok":
                warnings.append(f"{status.source}: {status.status} ({status.detail or 'no data'}).")
        if self.mode == "demo":
            warnings.append(
                "DEMO: recommendation prices and routes are synthetic; no live price is mixed into demo rankings."
            )
        else:
            warnings.append("Numeric premium octane and membership eligibility may be unverified.")
        if vehicle and vehicle.fuel_recommendation:
            warnings.append(vehicle.fuel_recommendation.note)
        if len(selections) > 30:
            from gaswise.domain.pricing.comparison import distance_meters

            selections.sort(key=lambda s: distance_meters(query.origin, s.station.location))
            selections = selections[:30]
            warnings.append("Candidate limit: only the nearest 30 merged stations were routed.")
        results = []
        costs = {}
        consumption = fuel_model(query, vehicle)
        if vehicle is None and query.mpg is None and not query.fuel_cycles:
            warnings.append("No vehicle or MPG was provided; using the legacy 20 MPG assumption.")
        baseline_fuel = route_fuel(baseline, consumption)
        warnings.append(
            "Fuel uses aggregate MPG, not route-specific traffic/grade/weather simulation; "
            "traffic time affects time cost only."
        )

        async def evaluate(selection):
            station = selection.station
            age = (now - station.price_updated_at).total_seconds() / 60 if station.price_updated_at else None
            try:
                route = await self.provider.route(query.origin, destination, station.location)
            except ProviderError:
                warnings.append(f"Route unavailable for station {station.id}; excluded from ranking.")
                return None
            miles = Decimal(str(max(0, route.distance_meters - baseline.distance_meters))) / Decimal(
                "1609.344"
            )
            minutes = Decimal(str(max(0, route.duration_seconds - baseline.duration_seconds))) / 60
            purchase = comparison_price(station) * query.gallons
            reward = purchase * cashback_rate(station, query)
            net_purchase = purchase - reward
            trip_fuel = route_fuel(route, consumption)
            extra_fuel = max(Decimal(0), trip_fuel - baseline_fuel)
            detour = extra_fuel * comparison_price(station)
            time = (minutes + query.stop_minutes) / 60 * query.time_value_per_hour
            low, high, spread, agreement, quality, count = comparable_prices(selection, now)
            multiplier = query.gallons * (1 - cashback_rate(station, query)) + extra_fuel
            offset = time if query.strategy == "best_value" else Decimal(0)
            # Preserve full precision for ordering and break-even decisions.
            costs[selection.key] = {
                "detour": detour,
                "time": time,
                "actual": net_purchase + detour,
                "generalized": net_purchase + detour + time,
                "upper": high * multiplier + time,
                "minutes": minutes,
                "lower_fuel": low * multiplier,
                "upper_fuel": high * multiplier,
            }
            comparison = PriceComparison(
                station_key=selection.key,
                selected_source=station.source,
                selection_reason=selection.reason,
                evidence=selection.evidence,
                eligible_source_count=count,
                price_spread=spread,
                agreement=agreement,
                quality=quality,
                comparable_cost_min=money(low * multiplier + offset),
                comparable_cost_max=money(high * multiplier + offset),
            )
            return RankedStation(
                station=station,
                route=route,
                detour_miles=miles.quantize(Decimal("0.001")),
                extra_travel_minutes=minutes.quantize(Decimal("0.01")),
                stop_minutes=query.stop_minutes,
                purchase_cost=money(purchase),
                credit_cashback_amount=money(reward),
                net_purchase_cost=money(net_purchase),
                detour_fuel_cost=money(detour),
                detour_fuel_gallons=extra_fuel,
                mpg_used=consumption.mpg_used,
                fuel_consumption_basis=consumption.basis,
                route_fuel_gallons=trip_fuel,
                baseline_fuel_gallons=baseline_fuel,
                fuel_model=consumption,
                actual_fuel_cost=money(net_purchase + detour),
                time_cost=money(time),
                generalized_trip_cost=money(net_purchase + detour + time),
                price_age_minutes=max(0, age) if age is not None else None,
                freshness="unknown"
                if age is None
                else "fresh"
                if age <= 60
                else "aging"
                if age <= 360
                else "stale",
                price_comparison=comparison,
            )

        for result in await asyncio.gather(*(evaluate(s) for s in selections)):
            if result:
                results.append(result)
            else:
                excluded += 1
        if results:
            nearest = min(
                results,
                key=lambda r: (
                    costs[r.price_comparison.station_key]["minutes"],
                    costs[r.price_comparison.station_key]["actual"],
                    r.price_comparison.station_key,
                ),
            )
            reference = costs[nearest.price_comparison.station_key]
            for result in results:
                savings = net_purchase_price(nearest.station, query) - net_purchase_price(result.station, query)
                cost = costs[result.price_comparison.station_key]
                overhead = cost["detour"] - reference["detour"]
                time_overhead = cost["time"] - reference["time"]
                fuel_savings = savings * query.gallons - overhead
                generalized_savings = fuel_savings - time_overhead
                result.break_even = BreakEven(
                    reference_station_key=nearest.price_comparison.station_key,
                    reference_station_id=nearest.station.id,
                    reference_station_name=nearest.station.name,
                    price_savings_per_gallon=savings,
                    additional_fuel_cost=money(overhead),
                    additional_time_cost=money(time_overhead),
                    fuel_only_gallons=max(Decimal(0), overhead) / savings if savings > 0 else None,
                    including_time_gallons=max(Decimal(0), overhead + time_overhead) / savings
                    if savings > 0
                    else None,
                    fuel_savings_at_requested_gallons=money(fuel_savings),
                    generalized_savings_at_requested_gallons=money(generalized_savings),
                    worthwhile_fuel_only=fuel_savings > 0,
                    worthwhile_including_time=generalized_savings > 0,
                )
                if savings > 0:
                    if query.strategy == "best_value":
                        overhead += time_overhead
                    result.break_even_gallons_vs_nearest = money(max(Decimal(0), overhead) / savings)

        def cost_of(row):
            return costs[row.price_comparison.station_key]

        keys = {
            "cheapest_overall": lambda r: (
                cost_of(r)["actual"],
                cost_of(r)["minutes"],
                r.price_comparison.station_key,
            ),
            "fastest_stop": lambda r: (
                cost_of(r)["minutes"],
                cost_of(r)["actual"],
                r.price_comparison.station_key,
            ),
            # Conservative choice under conflicting prices; observed range is not a probability interval.
            "best_value": lambda r: (
                cost_of(r)["upper"],
                cost_of(r)["minutes"],
                r.price_comparison.station_key,
            ),
            "on_my_route": lambda r: (
                cost_of(r)["actual"],
                cost_of(r)["minutes"],
                r.price_comparison.station_key,
            ),
        }
        margin = query.top_tier_margin_per_gallon * query.gallons

        def prefer_top_tier(ordered):
            """Cost stays primary: a TOP TIER station only leads when within the margin of the best."""
            if not query.prefer_top_tier or not ordered or ordered[0].station.top_tier_brand:
                return ordered, None
            best = cost_of(ordered[0])["upper"]
            for index, row in enumerate(ordered[1:], start=1):
                extra = cost_of(row)["upper"] - best
                if extra > margin:
                    break
                if row.station.top_tier_brand:
                    note = TopTierPreference(
                        station_name=ordered[0].station.name, extra_cost=money(extra), margin=money(margin)
                    )
                    return [row, *ordered[:index], *ordered[index + 1 :]], note
            return ordered, None

        recommendations = {}
        leaderboards = {}
        for strategy, key in keys.items():
            available = query.trip_mode == "on_route" or strategy != "on_my_route"
            ordered = sorted(results, key=key) if available else []
            preference = None
            if strategy == "best_value":
                ordered, preference = prefer_top_tier(ordered)
            # Decision ranges must use the category's cost basis, independent of
            # the user's selected strategy. These are copies, with no new routes.
            for index, row in enumerate(ordered):
                row = row.model_copy(deep=True)
                delta = cost_of(row)["time"] if strategy == "best_value" else Decimal(0)
                row.price_comparison.comparable_cost_min = money(cost_of(row)["lower_fuel"] + delta)
                row.price_comparison.comparable_cost_max = money(cost_of(row)["upper_fuel"] + delta)
                ordered[index] = row
            leaderboards[strategy] = ordered[:3]
            winner = ordered[0] if ordered else None
            recommendations[strategy] = StrategyRecommendation(
                station_key=winner.price_comparison.station_key if winner else None,
                station=winner.station if winner else None,
                actual_fuel_cost=winner.actual_fuel_cost if winner else None,
                generalized_trip_cost=winner.generalized_trip_cost if winner else None,
                extra_travel_minutes=winner.extra_travel_minutes if winner else None,
                top_tier_preferred_over=preference,
                decision=decide(ordered, statuses, strategy) if available else None,
                unavailable_reason="requires_on_route_trip"
                if not available
                else "no_eligible_stations"
                if not winner
                else None,
            )
        results.sort(key=keys[query.strategy])
        if query.strategy == "best_value":
            results, _ = prefer_top_tier(results)
        decision = decide(results, statuses, query.strategy)
        return SearchResult(
            applied_octane_aki=query.required_octane,
            octane_policy=query.octane_policy,
            generated_at=now,
            mode=self.mode,
            strategy=query.strategy,
            baseline_route=baseline,
            results=results[: query.max_results],
            warnings=warnings,
            excluded_count=excluded,
            source_statuses=statuses,
            decision=decision,
            recommendations=recommendations,
            leaderboards=leaderboards,
            vehicle=vehicle,
        )


def decide(results, statuses, strategy):
    if not results:
        return Decision(
            recommended_station_id=None,
            status="no_eligible_stations",
            reason="No eligible station with a usable route.",
        )
    winner = results[0]
    others = results[1:]
    if strategy == "fastest_stop":
        return Decision(
            recommended_station_id=winner.station.id,
            status="uncertain",
            reason="Fastest estimated route among candidates; queues and stop durations are not measured.",
        )
    if all(r.price_comparison.eligible_source_count == 1 for r in results):
        state, reason = (
            "single_source",
            "Comparable purchase conditions have only one source per station; price accuracy is not corroborated.",
        )
    elif (
        others
        and all(r.price_comparison.quality == "corroborated" and r.freshness == "fresh" for r in results)
        and all(s.status == "ok" for s in statuses)
        and winner.price_comparison.comparable_cost_max
        < min(r.price_comparison.comparable_cost_min for r in others)
    ):
        state, reason = (
            "robust",
            "Winner stays cheaper throughout the observed comparable quote ranges, among these candidates. This is not an accuracy guarantee.",
        )
    else:
        state, reason = (
            "uncertain",
            "Observed cost ranges overlap, sources conflict, or freshness/purchase conditions/coverage are incomplete; confirm price before a detour.",
        )
    nominal = winner.generalized_trip_cost if strategy == "best_value" else winner.actual_fuel_cost
    runner = (
        (others[0].generalized_trip_cost if strategy == "best_value" else others[0].actual_fuel_cost)
        if others
        else None
    )
    return Decision(
        recommended_station_id=winner.station.id,
        status=state,
        reason=reason,
        savings_vs_runner_up=money(runner - nominal) if runner is not None else None,
    )
