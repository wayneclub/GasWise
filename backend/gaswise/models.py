from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Point(Model):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Search(Model):
    origin: Point
    destination: Point | None = None
    trip_mode: Literal["round_trip", "on_route"] = "round_trip"
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] = "premium"
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    required_octane: int | None = Field(default=None, ge=87, le=100)
    gallons: Decimal = Field(default=Decimal(10), gt=0, le=100)
    mpg: Decimal = Field(default=Decimal(20), gt=0, le=200)
    time_value_per_hour: Decimal = Field(default=Decimal(0), ge=0, le=500)
    radius_meters: float = Field(default=10000, ge=100, le=50000)
    max_results: int = Field(default=5, ge=1, le=10)
    payment_type: Literal["cash", "credit"] = "credit"
    preferred_sources: list[str] = Field(
        default_factory=lambda: ["gasbuddy_web", "gasbuddy", "google_places"], max_length=10
    )
    memberships: list[str] = Field(default_factory=list, max_length=10)
    strategy: Literal["cheapest_overall", "fastest_stop", "best_value", "on_my_route"] = "cheapest_overall"
    max_price_age_minutes: int = Field(default=1440, ge=1, le=10080)
    stop_minutes: Decimal = Field(default=Decimal(5), ge=0, le=60)

    @model_validator(mode="after")
    def route_required(self):
        if (self.trip_mode == "on_route" or self.strategy == "on_my_route") and self.destination is None:
            raise ValueError("destination is required for on-route search")
        if self.strategy == "on_my_route" and self.trip_mode != "on_route":
            raise ValueError("on_my_route requires trip_mode=on_route")
        return self


class GooglePriceSearch(Model):
    origin: Point
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] = "premium"
    radius_meters: float = Field(default=5000, ge=100, le=50000)
    max_results: int = Field(default=20, ge=1, le=20)


class GooglePrices(Model):
    stations: list["Station"]
    source: Literal["google_places"] = "google_places"
    attribution: str = "Google Maps"
    warnings: list[str] = Field(default_factory=lambda: [
        "Only stations with a matching USD fuel price are returned; coverage is not guaranteed.",
        "Premium does not verify 91 octane; payment conditions are unknown.",
    ])


class GasBuddySearch(Model):
    search: str | None = Field(default=None, min_length=1, max_length=200)
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    origin: Point | None = None
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] = "premium"
    payment_type: Literal["cash", "credit", "cash_or_credit"] = "credit"
    brand_id: int | None = Field(default=None, gt=0)
    max_price_age_minutes: int | None = Field(default=None, ge=1, le=10080)
    max_results: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def location_required(self):
        if self.search is not None:
            self.search = self.search.strip()
            if not self.search:
                raise ValueError("search must not be blank")
        if self.search and self.postal_code:
            raise ValueError("provide search or postal_code, not both")
        if not self.search and not self.postal_code and self.origin is None:
            raise ValueError("search, postal_code or origin is required")
        return self


def gasbuddy_variables(query, fuel):
    term = getattr(query, "search", None) or query.postal_code
    variables = {"fuel": fuel, "maxAge": 0, "search": term}
    if getattr(query, "brand_id", None) is not None:
        variables["brandId"] = query.brand_id
    if term is None and query.origin is not None:
        variables.update(lat=query.origin.lat, lng=query.origin.lng)
    return variables


class Station(Model):
    id: str = Field(min_length=1, max_length=200)
    canonical_id: str | None = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    location: Point
    address: str | None = None
    price_per_gallon: Decimal = Field(gt=0)
    currency: Literal["USD"] = "USD"
    unit: Literal["US_gallon"] = "US_gallon"
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"]
    octane: int | None = None
    price_updated_at: AwareDatetime | None = None
    fetched_at: AwareDatetime
    source: str
    payment_type: Literal["cash", "credit", "unknown"] = "unknown"
    membership_required: str | None = None
    attribution: list[str] = Field(default_factory=list)


class Route(Model):
    distance_meters: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    source: str


class RankedStation(Model):
    station: Station
    route: Route
    detour_miles: Decimal
    extra_travel_minutes: Decimal
    stop_minutes: Decimal
    purchase_cost: Decimal
    detour_fuel_cost: Decimal
    actual_fuel_cost: Decimal
    time_cost: Decimal
    generalized_trip_cost: Decimal
    price_age_minutes: float | None
    freshness: Literal["fresh", "aging", "stale", "unknown"]
    break_even_gallons_vs_nearest: Decimal | None = None
    price_comparison: "PriceComparison | None" = None


class SearchResult(Model):
    generated_at: datetime
    mode: Literal["demo", "google"]
    strategy: str
    baseline_route: Route
    results: list[RankedStation]
    warnings: list[str]
    excluded_count: int
    source_statuses: list["SourceStatus"] = Field(default_factory=list)
    decision: "Decision | None" = None


class SourceStatus(Model):
    source: str
    status: Literal["ok", "unavailable", "not_configured"]
    quote_count: int = 0
    detail: str | None = None


class PriceEvidence(Model):
    source: str
    provider_station_id: str
    price_per_gallon: Decimal
    price_updated_at: datetime | None
    payment_type: Literal["cash", "credit", "unknown"]
    octane: int | None
    eligible: bool
    exclusion_reason: str | None = None
    comparable: bool = False
    comparison_exclusion_reason: str | None = None


class PriceComparison(Model):
    station_key: str
    selected_source: str
    selection_reason: str
    evidence: list[PriceEvidence]
    eligible_source_count: int
    price_spread: Decimal
    agreement: Literal["single_source", "consistent", "conflicting"]
    quality: Literal["corroborated", "limited", "disputed"]
    comparable_cost_min: Decimal
    comparable_cost_max: Decimal


class Decision(Model):
    recommended_station_id: str | None
    status: Literal["robust", "uncertain", "single_source", "no_eligible_stations"]
    reason: str
    savings_vs_runner_up: Decimal | None = None


RankedStation.model_rebuild()
SearchResult.model_rebuild()


class GasBuddyQuote(Model):
    membership_required: str | None = None
    id: str
    name: str
    address: str
    street: str
    city: str
    region: str
    postal_code: str
    price_per_gallon: Decimal = Field(gt=0)
    currency: Literal["USD"] = "USD"
    unit: Literal["US_gallon"] = "US_gallon"
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"]
    octane: int | None = None
    payment_type: Literal["cash", "credit"]
    price_updated_at: AwareDatetime | None
    fetched_at: AwareDatetime
    report_kind: Literal["datafeed", "community", "unknown"]
    source: Literal["gasbuddy_web"] = "gasbuddy_web"
    source_url: str


class GasBuddyPrices(Model):
    transport: Literal["http", "browser", "session_http"] = "http"
    fetched_at: AwareDatetime
    postal_code: str | None = None
    search: str | None = None
    prices: list[GasBuddyQuote]
    status: Literal["ok"] = "ok"
    partial: bool
    warnings: list[str]


class GasBuddyBrand(Model):
    brand_id: int
    slug: str
    name: str


class GasBuddyBrands(Model):
    source: Literal["gasbuddy_web"] = "gasbuddy_web"
    verified_on: str
    source_url: str
    exhaustive: bool = False
    all_brands: dict[str, str | None] = Field(
        default_factory=lambda: {"name": "All Station Brands", "brand_id": None}
    )
    brands: list[GasBuddyBrand]
