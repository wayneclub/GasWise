from fastapi import APIRouter, Depends, HTTPException

from gaswise.api.dependencies import authorize, get_services
from gaswise.app.runtime import Services
from gaswise.contracts.quality import TopTierList

router = APIRouter()


@router.get("/v1/quality/top-tier", response_model=TopTierList, dependencies=[Depends(authorize)])
async def top_tier_brands(*, services: Services = Depends(get_services)):
    """Current TOP TIER brand list and where it came from. Served from memory; no upstream call."""
    if services.top_tier is None:
        raise HTTPException(503, "top_tier_not_configured")
    return services.top_tier.current()
