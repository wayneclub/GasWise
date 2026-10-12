from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

from gaswise.contracts.common import Model


class VehicleProfile(Model):
    id: int = Field(gt=0)
    year: int = Field(ge=1984, le=2100)
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    transmission: str
    drive: str
    engine_liters: Decimal | None = Field(default=None, gt=0)
    cylinders: int | None = Field(default=None, gt=0)
    powertrain: Literal["gasoline", "diesel", "hybrid"]
    fuel_type: str
    city_mpg: Decimal = Field(gt=0, le=200)
    highway_mpg: Decimal = Field(gt=0, le=200)
    combined_mpg: Decimal = Field(gt=0, le=200)
    source: Literal["fueleconomy_gov"] = "fueleconomy_gov"
    fetched_at: AwareDatetime
    fuel_recommendation: "VehicleFuelRecommendation | None" = None


class VehicleFuelRecommendation(Model):
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"]
    source: Literal[
        "fueleconomy_gov", "manufacturer_manual", "specification_consensus", "fuel_grade_policy"
    ] = "fueleconomy_gov"
    evidence: str
    minimum_octane_aki: int | None = None
    recommended_octane_aki: int | None = None
    temporary_octane_aki: int | None = None
    source_urls: list[str] = Field(default_factory=list)
    octane_aki: int | None = None
    manufacturer_requirement_verified: bool = False
    assessment_status: Literal[
        "not_assessed", "manufacturer_verified", "agreement", "single_source", "conflict"
    ] = "not_assessed"
    specification_evidence: list["FuelSpecificationEvidence"] = Field(default_factory=list)
    assessment_warnings: list[str] = Field(default_factory=list)
    note: str = "EPA catalog fuel grade; exact minimum octane requires manufacturer or fuel-door evidence."


class FuelSpecificationEvidence(Model):
    source: Literal["fueleconomy_gov", "edmunds", "hertz"]
    source_group: str
    status: Literal["matched", "mismatch", "unavailable", "ambiguous"]
    fuel_grade: Literal["regular", "midgrade", "premium", "diesel"] | None = None
    requirement: Literal["recommended", "required", "unspecified"] = "unspecified"
    source_url: str
    observed_label: str | None = None
    numeric_octane_aki: int | None = None


class FuelAssessmentRequest(Model):
    vehicle_id: int = Field(gt=0, le=1000000)
    hertz_listing_url: str | None = Field(default=None, max_length=2000)

    @field_validator("hertz_listing_url")
    @classmethod
    def valid_hertz_url(cls, value):
        from gaswise.domain.validation.urls import validate_hertz_listing_url

        if value is not None:
            try:
                validate_hertz_listing_url(value)
            except ValueError:
                raise ValueError("Only public HTTPS Hertz vehicle listing URLs are accepted.") from None
        return value


class FuelAssessment(Model):
    vehicle: VehicleProfile
    target_octane_aki: int | None = None
    target_basis: Literal[
        "manufacturer_minimum", "manufacturer_normal_recommendation", "specification_estimate", "unresolved"
    ]
    hertz_status: Literal["not_requested", "matched", "mismatch", "unavailable"] = "not_requested"
    hertz_recommended_grade: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VehicleResolveRequest(Model):
    text: str = Field(default="", max_length=200)
    year: int | None = Field(default=None, ge=1984, le=2100)
    make: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    body_style: Literal["coupe", "convertible", "wagon", "other"] | None = None
    drivetrain: Literal["standard", "4matic"] | None = None
    catalog_model: str | None = Field(default=None, min_length=1, max_length=200)
    option_vehicle_id: int | None = Field(default=None, gt=0, le=1000000)


class VehicleChoice(Model):
    value: str
    label: str


class VehicleResolution(Model):
    status: Literal["needs_input", "no_match", "resolved"]
    year: int | None = None
    make: str | None = None
    question: str | None = None
    answer_field: str | None = None
    choices: list[VehicleChoice] = Field(default_factory=list)
    matched_models: list[str] = Field(default_factory=list)
    vehicle: VehicleProfile | None = None
    fuel_recommendation: VehicleFuelRecommendation | None = None
    selection: VehicleResolveRequest | None = None
    missing_fields: list[str] = Field(default_factory=list)


class VinRequest(Model):
    vin: str = Field(min_length=17, max_length=17)
    model_year: int | None = Field(default=None, ge=1984, le=2100)
    vehicle_id: int | None = Field(default=None, gt=0, le=1000000)

    @field_validator("vin", mode="before")
    @classmethod
    def valid_vin(cls, value):
        import re

        if not isinstance(value, str) or not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", value.upper()):
            raise ValueError("VIN requires 17 ASCII characters excluding I, O and Q")
        return value.upper()


class VinDecoded(Model):
    vin_masked: str
    source: Literal["nhtsa_vpic"] = "nhtsa_vpic"
    fetched_at: AwareDatetime
    check_digit_matches: bool
    error_codes: list[str]
    year: int | None = None
    make: str | None = None
    model: str | None = None
    series: str | None = None
    trim: str | None = None
    body_class: str | None = None
    drive: str | None = None
    engine_liters: Decimal | None = None
    engine_model: str | None = None
    cylinders: int | None = None
    fuel_primary: str | None = None
    fuel_secondary: str | None = None
    transmission: str | None = None
    transmission_speeds: int | None = None
    electrification: str | None = None


class VinResolution(Model):
    decoded: VinDecoded
    fuel_status: Literal["unknown", "epa_catalog", "manufacturer_manual", "specification_estimate"] = (
        "unknown"
    )
    mpg_status: Literal["unknown", "needs_confirmation", "confirmed"] = "unknown"
    status: Literal["decoded", "needs_input", "resolved", "no_match", "unsupported", "partial"]
    question: str | None = None
    choices: list[VehicleChoice] = Field(default_factory=list)
    vehicle: VehicleProfile | None = None
    fuel_recommendation: VehicleFuelRecommendation | None = None
    warnings: list[str] = Field(default_factory=list)
    upstream_calls: dict[str, int] = Field(default_factory=dict)


class PlateRequest(Model):
    plate: str = Field(min_length=1, max_length=12)
    state: str = Field(min_length=2, max_length=2)
    vehicle_id: int | None = Field(default=None, gt=0, le=1000000)

    @field_validator("plate", mode="before")
    @classmethod
    def normalize_plate(cls, value):
        import re

        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9 -]{1,12}", value):
            raise ValueError("Plate requires ASCII letters and digits; spaces and hyphens are allowed")
        value = value.upper().replace(" ", "").replace("-", "")
        if not value or len(value) > 10:
            raise ValueError("Plate requires 1 to 10 letters/digits")
        return value

    @field_validator("state", mode="before")
    @classmethod
    def us_state(cls, value):
        states = set(
            "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
        )
        if not isinstance(value, str) or value.upper() not in states:
            raise ValueError("A supported two-letter US state or DC code is required")
        return value.upper()


class PlateResolution(Model):
    plate_masked: str
    state: str
    source: Literal["vehicle_databases", "autozone"] = "vehicle_databases"
    source_make: str | None = None
    source_model: str | None = None
    source_year: int | None = None
    fetched_at: AwareDatetime
    resolution: VinResolution


class VehicleMenuItem(Model):
    text: str
    value: str


class VehicleMenu(Model):
    items: list[VehicleMenuItem]
    source: Literal["fueleconomy_gov"] = "fueleconomy_gov"
    warning: str = (
        "Catalog may include unsupported EV, PHEV or alternative-fuel vehicles; validate the selected record."
    )


VehicleProfile.model_rebuild()
VehicleFuelRecommendation.model_rebuild()
FuelSpecificationEvidence.model_rebuild()
FuelAssessmentRequest.model_rebuild()
FuelAssessment.model_rebuild()
VehicleResolveRequest.model_rebuild()
VehicleChoice.model_rebuild()
VehicleResolution.model_rebuild()
VinRequest.model_rebuild()
VinDecoded.model_rebuild()
VinResolution.model_rebuild()
PlateRequest.model_rebuild()
PlateResolution.model_rebuild()
VehicleMenuItem.model_rebuild()
VehicleMenu.model_rebuild()
