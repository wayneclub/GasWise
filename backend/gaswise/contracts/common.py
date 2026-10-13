from decimal import Decimal
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, hide_input_in_errors=True)


class Point(Model):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class FuelCycle(Model):
    """Same vehicle, non-overlapping full-to-full tank interval; not this stop's purchase."""

    distance_miles: Decimal = Field(gt=0, le=10000)
    consumed_gallons: Decimal = Field(gt=0, le=500)


class Station(Model):
    id: str = Field(min_length=1, max_length=200)
    canonical_id: str | None = Field(default=None, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    rating_source: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    octane_inference: dict[str, Any] | None = None
    name: str = Field(min_length=1, max_length=200)
    location: Point
    address: str | None = None
    price_per_gallon: Decimal = Field(gt=0)
    comparison_price_per_gallon: Decimal | None = Field(default=None, gt=0, description="Estimated comparison price; original quote is preserved in price_per_gallon.")
    payment_price_adjustment: Decimal = Field(default=Decimal(0), ge=0, le=1)
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
    open_now: bool | None = Field(
        default=None, description="Source-reported or source-hours status at fetched_at; null is unknown."
    )
    business_status: Literal["operational", "temporarily_closed", "permanently_closed"] | None = None
    top_tier_brand: str | None = Field(
        default=None, max_length=200, description="Matched TOP TIER licensed brand (brand-level license)."
    )


class Route(Model):
    distance_meters: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    source: str
    fetched_at: AwareDatetime | None = None
    duration_basis: Literal["provider_estimate", "maps_estimate", "maps_traffic_estimate", "geometric_estimate"] = (
        "provider_estimate"
    )
    upstream_http_requests: int = Field(default=0, ge=0)


class SourceStatus(Model):
    source: str
    status: Literal["ok", "unavailable", "not_configured"]
    quote_count: int = 0
    detail: str | None = None


Model.model_rebuild()
Point.model_rebuild()
FuelCycle.model_rebuild()
Station.model_rebuild()
Route.model_rebuild()
SourceStatus.model_rebuild()
