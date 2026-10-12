"""Parts identification and fitment contracts, independent of supplier adapters."""

from typing import Literal

from pydantic import Field, computed_field, model_validator

from gaswise.contracts.common import Model
from gaswise.contracts.vehicles import PlateRequest, VinDecoded, VinRequest
from gaswise.domain.validation.urls import amazon_url, validate_oreilly_url


class PartsRequest(Model):
    amazon_url: str = Field(max_length=4000)
    vin: VinRequest | None = None
    plate: PlateRequest | None = None
    brand: str | None = Field(default=None, max_length=80)
    part_number: str | None = Field(default=None, max_length=80)
    oreilly_product_url: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_request(self):
        self.amazon_url = amazon_url(self.amazon_url)
        if self.oreilly_product_url:
            self.oreilly_product_url = validate_oreilly_url(self.oreilly_product_url)
        if (self.vin is None) == (self.plate is None):
            raise ValueError("Provide exactly one VIN or plate identity")
        if bool(self.brand) != bool(self.part_number):
            raise ValueError("Brand and part_number must be supplied together")
        return self


class PartsEvidence(Model):
    source: Literal["amazon", "manufacturer", "autozone", "oreilly"]
    status: Literal["matched", "incompatible", "conditional", "no_match", "ambiguous", "unavailable"]
    scope: Literal["product_identity", "catalog_application", "engine_application", "vehicle_fitment"]
    source_url: str
    detail: str | None = None
    brand: str | None = None
    part_number: str | None = None
    catalog_product_id: str | None = None
    conditions: list[str] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)
    application_descriptions: list[str] = Field(default_factory=list)
    product_relation: Literal["direct_product", "interchange_candidate", "verified_interchange"] = (
        "direct_product"
    )
    interchange_source_url: str | None = None
    referenced_part_number: str | None = None
    replacement_candidates: list[dict[str, str]] = Field(default_factory=list)
    lookup_stages: list[str] = Field(default_factory=list)
    provider_error: str | None = None


class PartsCrossCheck(Model):
    status: Literal["supported", "rejected", "conflict", "insufficient"] = "insufficient"
    verified_sources: list[Literal["autozone", "oreilly"]] = Field(default_factory=list)
    source_statuses: dict[str, str] = Field(default_factory=dict)
    detail: str = (
        "No verified application for the requested product; retailer count is not a fitment requirement."
    )


class PartsResult(Model):
    status: Literal["compatible", "incompatible", "needs_confirmation", "conflict"]
    amazon_url: str
    product_status: Literal[
        "identified", "unavailable", "ambiguous", "unsupported", "user_supplied_unverified", "conflict"
    ]
    title: str | None = None
    brand: str | None = None
    part_number: str | None = None
    model_number: str | None = None
    category: str | None = None
    verification_scope: Literal[
        "unresolved", "catalog_application", "engine_application", "vehicle_fitment"
    ] = "unresolved"
    evidence: list[PartsEvidence] = Field(default_factory=list)
    cross_check: PartsCrossCheck = Field(default_factory=PartsCrossCheck)
    missing_fields: list[str] = Field(default_factory=list)
    vehicle: VinDecoded
    source_urls: list[str] = Field(default_factory=list)
    applications: list[dict[str, str]] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def usage_decision(self) -> Literal["verified_fit", "do_not_use", "verification_required"]:
        """Keep an unresolved lookup distinct from explicit rejection, but block both."""
        if self.status == "compatible":
            return "verified_fit"
        if self.status == "incompatible":
            return "do_not_use"
        return "verification_required"

    @computed_field
    @property
    def fitment_confirmed(self) -> bool:
        return self.usage_decision == "verified_fit"


class PartsSearchRequest(Model):
    keyword: str = Field(min_length=2, max_length=100)
    vin: VinRequest | None = None
    plate: PlateRequest | None = None
    max_results: int = Field(default=3, ge=1, le=6)

    @model_validator(mode="after")
    def valid_identity(self):
        self.keyword = " ".join(self.keyword.split())
        if len(self.keyword) < 2 or (self.vin is None) == (self.plate is None):
            raise ValueError("A keyword and exactly one VIN or plate identity are required")
        return self


class PartCandidate(Model):
    name: str
    brand: str
    part_number: str
    product_url: str
    status: Literal["compatible", "incompatible", "needs_confirmation"]
    evidence: PartsEvidence


class PartsSearchResult(Model):
    keyword: str
    vehicle: VinDecoded
    items: list[PartCandidate]
    source: Literal["autozone"] = "autozone"
    source_status: Literal["ok", "no_match", "unavailable", "not_configured"]
    candidate_count: int = 0
    partial: bool = True
    warnings: list[str] = Field(default_factory=list)
