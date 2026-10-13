from fastapi import APIRouter, Depends, HTTPException, Query

from gaswise.api.dependencies import authorize, get_operations, get_services, get_settings
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.app.settings import Settings
from gaswise.contracts.search import Search
from gaswise.contracts.sources import (
    GasBuddyBrands,
    GasBuddyPrices,
    GasBuddySearch,
    GooglePrices,
    GooglePriceSearch,
    MapsWebPrices,
    MapsWebSearch,
    WazePriceSearch,
)
from gaswise.providers.gasbuddy.brands import BRANDS, SOURCE_URL, VERIFIED_ON
from gaswise.providers.pricing.aaa import STATES, AAASnapshot

router = APIRouter()


@router.get("/v1/sources", dependencies=[Depends(authorize)])
async def price_sources(*, services: Services = Depends(get_services)):
    return {
        "sources": services.source_registry.describe(),
        "contract": "gaswise.price-feed.v1",
        "regional_average_sources": [
            {
                "source_id": "aaa",
                "enabled": True,
                "endpoint": "/v1/sources/aaa/averages",
                "update_frequency": "daily",
            }
        ],
    }


@router.get("/v1/sources/refresh-status", dependencies=[Depends(authorize)])
async def hot_refresh_status(
    *, services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    if services.smart.hot_refresh is None:
        return {"enabled": False}
    return await operations.run(services.smart.hot_refresh.status)


@router.get("/v1/sources/aaa/averages", response_model=AAASnapshot, dependencies=[Depends(authorize)])
async def aaa_averages(
    state: str = Query(default="CA", min_length=2, max_length=2),
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    state = state.upper()
    if state not in STATES:
        raise HTTPException(422, "invalid_us_state")
    return await operations.run(lambda: services.aaa.averages(state))


@router.post("/v1/prices", dependencies=[Depends(authorize)])
async def prices(
    query: Search,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    snapshot = await operations.run(lambda: services.price_provider.snapshot(query))
    return {"stations": snapshot.stations, "source_statuses": snapshot.statuses}


@router.post("/v1/sources/google/prices", response_model=GooglePrices, dependencies=[Depends(authorize)])
async def google_prices(
    query: GooglePriceSearch,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    if services.google_prices is None:
        raise HTTPException(503, "google_places_not_configured")
    stations = await operations.run(lambda: services.google_prices.stations(query))
    return GooglePrices(stations=stations)


@router.post(
    "/v1/sources/google-maps-web/prices", response_model=MapsWebPrices, dependencies=[Depends(authorize)]
)
async def maps_web_prices(
    query: MapsWebSearch,
    *,
    services: Services = Depends(get_services),
    settings: Settings = Depends(get_settings),
    operations: OperationRunner = Depends(get_operations),
):
    if not settings.api_token.get_secret_value():
        raise HTTPException(503, "api_token_required_for_web_source")
    return await operations.run(lambda: services.maps_web.prices(query))


@router.post("/v1/sources/waze/prices", dependencies=[Depends(authorize)])
async def waze_prices(
    query: WazePriceSearch,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    if services.waze is None:
        raise HTTPException(503, "waze_not_configured")
    rows = await operations.run(lambda: services.waze.prices(query))
    return {
        "source": "waze",
        "stations": rows,
        "warnings": [
            "Price payment conditions and pump-verified octane are unknown; sourced octane estimates are separate.",
            "Undocumented protocol; authentication credentials may expire or be revoked.",
        ],
    }


@router.get("/v1/sources/gasbuddy/brands", response_model=GasBuddyBrands, dependencies=[Depends(authorize)])
async def gasbuddy_brands():
    return GasBuddyBrands(verified_on=VERIFIED_ON, source_url=SOURCE_URL, brands=BRANDS)


@router.post("/v1/sources/gasbuddy/prices", response_model=GasBuddyPrices, dependencies=[Depends(authorize)])
async def gasbuddy_prices(
    query: GasBuddySearch,
    *,
    services: Services = Depends(get_services),
    settings: Settings = Depends(get_settings),
    operations: OperationRunner = Depends(get_operations),
):
    if not settings.gasbuddy_web_enabled:
        raise HTTPException(503, "gasbuddy_web_not_enabled")
    return await operations.run(lambda: services.gasbuddy_web.prices(query))
