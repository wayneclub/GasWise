from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from gaswise.contracts.common import Model, Point, Station


class GooglePriceSearch(Model):
    origin: Point
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] = "premium"
    radius_meters: float = Field(default=5000, ge=100, le=50000)
    max_results: int = Field(default=20, ge=1, le=20)


class GooglePrices(Model):
    stations: list["Station"]
    source: Literal["google_places"] = "google_places"
    attribution: str = "Google Maps"
    warnings: list[str] = Field(
        default_factory=lambda: [
            "Only stations with a matching USD fuel price are returned; coverage is not guaranteed.",
            "Premium does not verify 91 octane; payment conditions are unknown.",
        ]
    )


class MapsWebSearch(GooglePriceSearch):
    search_text: str = Field(default="gas stations", min_length=1, max_length=200)
    max_results: int = Field(default=20, ge=1, le=100)
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] = "regular"
    detail_limit: int = Field(default=0, ge=0, le=10)


class MapsWebStation(Model):
    place_id: str
    name: str
    location: Point
    address: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    rating_source: str | None = None
    distance_meters: float
    available_fuel_types: list[str]
    open_now: bool | None = None
    business_status: Literal["operational", "temporarily_closed", "permanently_closed"] | None = None
    opening_status: str | None = Field(default=None, max_length=200)


class MapsWebPrices(Model):
    source: Literal["google_maps_web"] = "google_maps_web"
    stations: list["Station"]
    all_prices: list["Station"] = Field(default_factory=list)
    inventory: list[MapsWebStation]
    warnings: list[str]
    authentication: Literal["anonymous", "session"] = "anonymous"
    detail_requests: int = 0
    upstream_http_requests: int = 1
    official_api_requests: int = 0


class WazePriceSearch(Model):
    origin: Point
    radius_meters: float = Field(default=5000, ge=100, le=50000)
    max_results: int = Field(default=20, ge=1, le=20)
    venue_id: str | None = Field(default=None, pattern=r"^venues\.[0-9.]+$", max_length=200)
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")


class GasBuddySearch(Model):
    max_pages: int = Field(default=1, ge=1, le=5)
    include_payment_variants: bool = False
    search: str | None = Field(default=None, min_length=1, max_length=200)
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    origin: Point | None = None
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"] = "premium"
    payment_type: Literal["cash", "credit", "cash_or_credit"] = "credit"
    brand_id: int | None = Field(default=None, gt=0)
    max_price_age_minutes: int | None = Field(default=None, ge=1, le=10080)
    max_results: int = Field(default=5, ge=1, le=100)

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
    page_requests: int = Field(default=1, ge=1, le=5)
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


GooglePriceSearch.model_rebuild()
GooglePrices.model_rebuild()
MapsWebSearch.model_rebuild()
MapsWebStation.model_rebuild()
MapsWebPrices.model_rebuild()
WazePriceSearch.model_rebuild()
GasBuddySearch.model_rebuild()
GasBuddyQuote.model_rebuild()
GasBuddyPrices.model_rebuild()
GasBuddyBrand.model_rebuild()
GasBuddyBrands.model_rebuild()
