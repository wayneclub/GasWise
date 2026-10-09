import asyncio
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from gaswise.comparison import comparable_prices, select_prices
from gaswise.models import Decision, PriceComparison, RankedStation, Route, Search, SearchResult, SourceStatus
from gaswise.providers.base import Provider, ProviderError
from gaswise.providers.multi import MultiSourceProvider


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SearchService:
    def __init__(self, provider: Provider, mode: str):
        self.provider, self.mode = provider, mode

    async def search(self, query: Search) -> SearchResult:
        destination = query.destination if query.trip_mode == "on_route" else query.origin
        baseline = (
            await self.provider.route(query.origin, destination)
            if query.trip_mode == "on_route"
            else Route(distance_meters=0, duration_seconds=0, source="no_trip")
        )
        if isinstance(self.provider, MultiSourceProvider):
            snapshot = await self.provider.snapshot(query)
            stations, statuses = snapshot.stations, snapshot.statuses
        else:
            stations = await self.provider.stations(query)
            sources = sorted({s.source for s in stations})
            statuses = [
                SourceStatus(
                    source=source, status="ok", quote_count=sum(s.source == source for s in stations)
                )
                for source in sources
            ]
        now = datetime.now(UTC)
        selections, excluded, warnings = select_prices(stations, query, now)
        warnings.append(
            "Costs assume fixed purchased gallons and station price for detour fuel; exclude tolls, queues and vehicle wear."
        )
        warnings.append(
            "Source agreement is a rule-based signal, not measured accuracy or proof of independent data feeds."
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
        if len(selections) > 30:
            from gaswise.comparison import distance_meters

            selections.sort(key=lambda s: distance_meters(query.origin, s.station.location))
            selections = selections[:30]
            warnings.append("Candidate limit: only the nearest 30 merged stations were routed.")
        results = []

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
            purchase = station.price_per_gallon * query.gallons
            detour = miles / query.mpg * station.price_per_gallon
            time = (minutes + query.stop_minutes) / 60 * query.time_value_per_hour
            low, high, spread, agreement, quality, count = comparable_prices(selection, now)
            multiplier = query.gallons + miles / query.mpg
            offset = time if query.strategy == "best_value" else Decimal(0)
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
                detour_fuel_cost=money(detour),
                actual_fuel_cost=money(purchase + detour),
                time_cost=money(time),
                generalized_trip_cost=money(purchase + detour + time),
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
            nearest = min(results, key=lambda r: r.extra_travel_minutes)
            for result in results:
                savings = nearest.station.price_per_gallon - result.station.price_per_gallon
                if savings > 0:
                    overhead = result.detour_fuel_cost - nearest.detour_fuel_cost
                    if query.strategy == "best_value":
                        overhead += result.time_cost - nearest.time_cost
                    result.break_even_gallons_vs_nearest = money(max(Decimal(0), overhead) / savings)
        key = {
            "cheapest_overall": lambda r: (r.actual_fuel_cost, r.extra_travel_minutes),
            "fastest_stop": lambda r: (r.extra_travel_minutes, r.actual_fuel_cost),
            # Conservative choice under conflicting prices; observed range is not a probability interval.
            "best_value": lambda r: (r.price_comparison.comparable_cost_max, r.extra_travel_minutes),
            "on_my_route": lambda r: (r.actual_fuel_cost, r.extra_travel_minutes),
        }[query.strategy]
        results.sort(key=key)
        decision = decide(results, statuses, query.strategy)
        return SearchResult(
            generated_at=now,
            mode=self.mode,
            strategy=query.strategy,
            baseline_route=baseline,
            results=results[: query.max_results],
            warnings=warnings,
            excluded_count=excluded,
            source_statuses=statuses,
            decision=decision,
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
