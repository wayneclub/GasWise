from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from gaswise.contracts.common import Model


class TopTierBrand(Model):
    name: str = Field(min_length=1, max_length=200)
    countries: list[str] = Field(max_length=40)


class TopTierList(Model):
    """TOP TIER licensed retail brands: an automaker-run voluntary standard, not a government rating."""

    program: Literal["TOP TIER Detergent Gasoline"] = "TOP TIER Detergent Gasoline"
    source_url: str
    page_modified_at: datetime | None = None
    fetched_at: AwareDatetime
    origin: Literal["bundled", "cache", "live"]
    brands: list[TopTierBrand] = Field(max_length=1000)
    note: str = (
        "Licensing is brand-level: every outlet and octane grade of a licensed brand qualifies, "
        "with or without a pump decal. GasWise matches stations by brand name."
    )
