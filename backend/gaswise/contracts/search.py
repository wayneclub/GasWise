from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from gaswise.contracts.common import FuelCycle, Model, Point, Route, SourceStatus, Station
from gaswise.contracts.vehicles import VehicleProfile


class RankOptions(Model):
    gallons: Decimal = Field(default=Decimal(10), gt=0, le=100)
    mpg: Decimal | None = Field(default=None, gt=0, le=200)
    fuel_cycles: list[FuelCycle] = Field(default_factory=list, max_length=30)
    time_value_per_hour: Decimal = Field(default=Decimal(0), ge=0, le=500)
    payment_type: Literal["cash", "credit", "cash_or_credit"] = "credit"
    credit_cashback_percent: Decimal = Field(default=Decimal(0), ge=0, le=100, description="User-estimated credit-card reward percentage on the fuel purchase only. Cash receives no reward; eligibility and reward caps are not verified.")
    allow_unknown_payment: bool = False
    unknown_payment_credit_markup: Decimal = Field(default=Decimal(0), ge=0, le=1, description="User assumption added to unknown-payment quotes for credit or all-payment comparison. Not a verified station surcharge.")
    memberships: list[str] = Field(default_factory=list, max_length=10)
    preferred_sources: list[str] = Field(
        default_factory=lambda: ["gasbuddy_web", "gasbuddy", "google_places"], max_length=10
    )
    strategy: Literal["cheapest_overall", "fastest_stop", "best_value", "on_my_route"] = "cheapest_overall"
    required_octane: int | None = Field(
        default=None, ge=87, le=100, description="Minimum accepted AKI; higher values qualify."
    )
    octane_policy: Literal["verified_only", "regional_estimate"] = "regional_estimate"
    max_price_age_minutes: int = Field(default=1440, ge=1, le=10080)
    stop_minutes: Decimal = Field(default=Decimal(5), ge=0, le=60)
    max_results: int = Field(default=5, ge=1, le=100)
    top_tier_only: bool = Field(
        default=False, description="Keep only stations matched to a TOP TIER licensed brand."
    )
    prefer_top_tier: bool = Field(
        default=True,
        description="Best value may pick a TOP TIER station whose cost is within the margin of the cheapest.",
    )
    top_tier_margin_per_gallon: Decimal = Field(
        default=Decimal("0.05"),
        ge=0,
        le=1,
        description="USD per purchased gallon a TOP TIER pick may cost more.",
    )
    opening_policy: Literal["exclude_closed", "require_open", "ignore"] = Field(
        default="exclude_closed",
        description="exclude_closed keeps unknown hours; require_open also excludes unknown hours.",
    )


class Search(RankOptions):
    origin: Point
    destination: Point | None = None
    trip_mode: Literal["round_trip", "on_route"] = "round_trip"
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] | None = None
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    current_state: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{2}$",
        description="US origin state fallback; station state takes precedence.",
    )
    vehicle_id: int | None = Field(default=None, gt=0, le=1000000)
    radius_meters: float = Field(default=10000, ge=100, le=50000)

    @model_validator(mode="after")
    def route_required(self):
        if self.fuel_type is None and self.vehicle_id is None:
            self.fuel_type = "premium"
        if (self.trip_mode == "on_route" or self.strategy == "on_my_route") and self.destination is None:
            raise ValueError("destination is required for on-route search")
        if self.strategy == "on_my_route" and self.trip_mode != "on_route":
            raise ValueError("on_my_route requires trip_mode=on_route")
        return self


class RegionalBenchmark(Model):
    state: str
    region: str
    scope: Literal["state", "metro"]
    fuel_type: str
    price_per_gallon: Decimal
    price_as_of: date
    retrieved_at: datetime
    source_url: str


class RankedStation(Model):
    station: Station
    regional_benchmark: RegionalBenchmark | None = None
    route: Route
    detour_miles: Decimal
    extra_travel_minutes: Decimal
    stop_minutes: Decimal
    purchase_cost: Decimal
    credit_cashback_amount: Decimal = Decimal(0)
    net_purchase_cost: Decimal | None = None
    detour_fuel_cost: Decimal
    actual_fuel_cost: Decimal
    time_cost: Decimal
    generalized_trip_cost: Decimal
    price_age_minutes: float | None
    freshness: Literal["fresh", "aging", "stale", "unknown"]
    break_even_gallons_vs_nearest: Decimal | None = None
    price_comparison: "PriceComparison | None" = None
    break_even: "BreakEven | None" = None
    detour_fuel_gallons: Decimal = Decimal(0)
    mpg_used: Decimal | None = None
    fuel_consumption_basis: Literal[
        "user_mpg_estimate", "full_tank_calibrated_estimate", "epa_combined_estimate"
    ] = "user_mpg_estimate"
    route_fuel_gallons: Decimal = Decimal(0)
    baseline_fuel_gallons: Decimal = Decimal(0)
    fuel_model: "FuelModelInfo | None" = None


class FuelModelInfo(Model):
    model_id: Literal["distance_fuel_balance_v1"] = "distance_fuel_balance_v1"
    basis: Literal["user_mpg_estimate", "full_tank_calibrated_estimate", "epa_combined_estimate"]
    mpg_used: Decimal
    calibration_cycles: int = 0
    calibration_miles: Decimal = Decimal(0)
    calibration_gallons: Decimal = Decimal(0)
    route_specific_efficiency: bool = False
    assumptions: list[str]
    vehicle: VehicleProfile | None = None


class BreakEven(Model):
    reference_station_key: str
    reference_station_id: str
    reference_station_name: str
    price_savings_per_gallon: Decimal
    additional_fuel_cost: Decimal
    additional_time_cost: Decimal
    fuel_only_gallons: Decimal | None
    including_time_gallons: Decimal | None
    fuel_savings_at_requested_gallons: Decimal
    generalized_savings_at_requested_gallons: Decimal
    worthwhile_fuel_only: bool
    worthwhile_including_time: bool


class StrategyRecommendation(Model):
    station_key: str | None
    station: Station | None
    actual_fuel_cost: Decimal | None
    generalized_trip_cost: Decimal | None
    extra_travel_minutes: Decimal | None
    top_tier_preferred_over: "TopTierPreference | None" = None
    decision: "Decision | None"
    unavailable_reason: str | None = None


class TopTierPreference(Model):
    """The cost-first winner that a TOP TIER station replaced, and what the preference costs."""

    station_name: str
    extra_cost: Decimal
    margin: Decimal


class SearchResult(Model):
    applied_octane_aki: int | None = None
    octane_policy: Literal["verified_only", "regional_estimate"] = "regional_estimate"
    generated_at: datetime
    mode: Literal["demo", "google", "prices_only"]
    strategy: str
    baseline_route: Route
    results: list[RankedStation]
    warnings: list[str]
    excluded_count: int
    source_statuses: list["SourceStatus"] = Field(default_factory=list)
    decision: "Decision | None" = None
    recommendations: dict[str, StrategyRecommendation] = Field(default_factory=dict)
    leaderboards: dict[str, list[RankedStation]] = Field(default_factory=dict)
    vehicle: VehicleProfile | None = None


class PriceEvidence(Model):
    source: str
    provider_station_id: str
    price_per_gallon: Decimal
    price_updated_at: datetime | None
    payment_type: Literal["cash", "credit", "unknown"]
    octane: int | None
    octane_inference: dict[str, Any] | None = None
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


Search.model_rebuild()
RankedStation.model_rebuild()
FuelModelInfo.model_rebuild()
BreakEven.model_rebuild()
TopTierPreference.model_rebuild()
StrategyRecommendation.model_rebuild()
SearchResult.model_rebuild()
PriceEvidence.model_rebuild()
PriceComparison.model_rebuild()
Decision.model_rebuild()
