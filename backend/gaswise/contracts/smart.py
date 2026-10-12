from pydantic import AwareDatetime, Field, computed_field

from gaswise.contracts.common import Model, Point, Route, SourceStatus, Station
from gaswise.contracts.search import RankOptions as RankOptions
from gaswise.contracts.search import RegionalBenchmark, Search, SearchResult
from gaswise.contracts.sources import GasBuddyQuote, MapsWebStation
from gaswise.contracts.vehicles import VehicleProfile


class SmartSearch(Search):
    force_refresh: bool = False
    gasbuddy_page_limit: int = Field(default=1, ge=1, le=5)
    station_lookup_limit: int = Field(default=0, ge=0, le=5)
    calculate_routes: bool = False
    route_limit: int = Field(default=5, ge=1, le=100)
    discovery_tiles: int = Field(default=1, ge=1, le=5)
    maps_detail_limit: int = Field(default=0, ge=0, le=5)


class SnapshotRoute(Model):
    via: Point
    route: Route


class SmartSnapshot(Model):
    query: Search
    stations: list[Station] = Field(max_length=500)
    source_statuses: list[SourceStatus] = Field(max_length=30)
    baseline: Route | None = None
    routes: list[SnapshotRoute] = Field(default_factory=list, max_length=100)
    collected_at: AwareDatetime
    expires_at: AwareDatetime
    warnings: list[str] = Field(default_factory=list, max_length=100)
    unlocated_gasbuddy: list[GasBuddyQuote] = Field(default_factory=list, max_length=100)
    inventory: list[MapsWebStation] = Field(default_factory=list, max_length=100)
    vehicle: VehicleProfile | None = None
    regional_averages: list[RegionalBenchmark] = Field(default_factory=list, max_length=200)


class SearchCoverage(Model):
    discovered: int
    priced: int
    eligible: int
    routed: int
    displayed: int
    exclusions: dict[str, int]
    station_statuses: dict[str, str]
    quote_indices: dict[str, int]


class SmartResult(Model):
    timings_ms: dict[str, float] = Field(default_factory=dict)
    cache_hits: int = Field(default=0, ge=0)
    snapshot: SmartSnapshot
    signature: str
    ranking: SearchResult | None = None
    upstream_calls: dict[str, int]

    @computed_field
    @property
    def coverage(self) -> SearchCoverage:
        from collections import Counter

        from gaswise.domain.pricing.comparison import (
            closed_reason,
            distance_meters,
            ineligible,
            select_prices,
        )
        query = self.snapshot.query
        now = self.ranking.generated_at if self.ranking else self.snapshot.collected_at
        groups = {}
        for station in self.snapshot.stations:
            groups.setdefault(station.canonical_id or f"{station.source}:{station.id}", []).append(station)
        selections, _, _ = select_prices(self.snapshot.stations, query, now)
        eligible = {s.key for s in selections}
        route_points = {(r.via.lat, r.via.lng) for r in self.snapshot.routes}
        routed = {s.key for s in selections if (s.station.location.lat, s.station.location.lng) in route_points}
        statuses, quote_indices = {}, {}
        selected = {s.key: s.station for s in selections}
        for key, records in groups.items():
            allowed = {"cash", "credit"} if query.payment_type == "cash_or_credit" else {query.payment_type}
            representative = selected.get(key) or min(records, key=lambda r: (
                0 if r.payment_type in allowed else 1 if r.payment_type == "unknown" else 2,
                -(r.price_updated_at.timestamp() if r.price_updated_at else 0),
            ))
            quote_indices[key] = next(i for i, r in enumerate(self.snapshot.stations) if r.source == representative.source and r.id == representative.id and r.payment_type == representative.payment_type and r.price_per_gallon == representative.price_per_gallon)
            if key in routed:
                statuses[key] = "routed"
            elif key in eligible:
                statuses[key] = "route_not_calculated"
            else:
                anchor = records[0]
                closed = closed_reason([r for r in records if distance_meters(anchor.location, r.location) <= 75], query)
                statuses[key] = closed or ineligible(representative, query, now) or "station_mapping_location_mismatch"
        for station in self.snapshot.inventory:
            statuses.setdefault(f"google_places:{station.place_id}", "station_closed" if station.open_now is False or station.business_status in {"temporarily_closed", "permanently_closed"} else "opening_status_unknown" if query.opening_policy == "require_open" and station.open_now is not True else "no_matching_fuel_price")
        exclusions = Counter(value for value in statuses.values() if value != "routed")
        return SearchCoverage(discovered=len(statuses), priced=len(groups), eligible=len(eligible), routed=len(routed), displayed=len(self.ranking.results) if self.ranking else 0, exclusions=dict(exclusions), station_statuses=statuses, quote_indices=quote_indices)


class SmartRerank(Model):
    snapshot: SmartSnapshot
    signature: str = Field(min_length=64, max_length=64)
    options: RankOptions


class SmartRouteRequest(Model):
    snapshot: SmartSnapshot
    signature: str = Field(min_length=64, max_length=64)
    route_limit: int = Field(default=5, ge=1, le=100)


SmartSearch.model_rebuild()
RankOptions.model_rebuild()
SnapshotRoute.model_rebuild()
SmartSnapshot.model_rebuild()
SmartResult.model_rebuild()
SmartRerank.model_rebuild()
SmartRouteRequest.model_rebuild()
