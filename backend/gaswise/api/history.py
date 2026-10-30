"""Read bounded public price observations without contacting providers."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, Field

from gaswise.api.dependencies import authorize, get_services
from gaswise.app.runtime import Services
from gaswise.contracts.common import Model
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.trend_analysis import analyze_station_history

router = APIRouter()


class HistoryRequest(Model):
    canonical_id: str | None = Field(default=None, min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    station_id: str = Field(min_length=1, max_length=200)
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"]
    days: Literal[7, 30, 90] = 30


class PriceObservation(Model):
    observation_kind: Literal["report", "daily_check"] = "report"
    source: str
    station_id: str
    payment_type: str
    condition: str
    price: str
    reported_at: AwareDatetime | None
    observed_at: AwareDatetime
    membership: str | None
    octane: int | None


class PriceBand(Model):
    min_price: str | None = None
    max_price: str | None = None
    median_price: str | None = None
    current_price: str | None = None
    percentile: float | None = None
    band: Literal["near_low", "mid_range", "near_high"] = "mid_range"
    is_cycle_low: bool = False
    is_cycle_high: bool = False
    advice: str = ""


class WeekendCycle(Model):
    day_of_week: str
    is_pre_weekend: bool = False
    pre_weekend_hike_risk: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"
    trend: Literal["rising", "falling", "stable"] = "stable"
    message: str = ""


class HistoryAnalysis(Model):
    price_band: PriceBand
    weekend_cycle: WeekendCycle
    observation_count: int


class PriceHistory(Model):
    observations: list[PriceObservation] = Field(max_length=1000)
    truncated: bool
    analysis: HistoryAnalysis | None = None


@router.post("/v1/prices/history", response_model=PriceHistory, response_model_exclude_none=True, dependencies=[Depends(authorize)])
async def price_history(body: HistoryRequest, services: Services = Depends(get_services)):
    cache = services.smart.shared_cache
    if cache is None:
        raise HTTPException(503, "price_history_unavailable")
    try:
        raw = await cache.price_history(body.canonical_id, body.source, body.station_id, body.fuel_type, body.days)
        observations = raw.get("observations", [])
        analysis = analyze_station_history(observations) if observations else None
        return {
            "observations": observations,
            "truncated": raw.get("truncated", False),
            "analysis": analysis,
        }
    except ProviderError:
        raise HTTPException(503, "price_history_unavailable") from None
