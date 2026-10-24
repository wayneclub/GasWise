from fastapi import APIRouter, Depends, HTTPException

from gaswise.api.dependencies import authorize, get_operations, get_services
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.contracts.smart import (
    ProgressiveSearchPoll,
    ProgressiveSearchState,
    SmartPriceRefresh,
    SmartRerank,
    SmartResult,
    SmartRouteRequest,
    SmartSearch,
)
from gaswise.domain.ports import ProviderError

router = APIRouter()


@router.post("/v1/smart/search-jobs/start", response_model=ProgressiveSearchState, dependencies=[Depends(authorize)])
async def smart_search_job_start(query: SmartSearch, *, services: Services = Depends(get_services)):
    if query.calculate_routes and services.smart.demo is None and services.smart.router is None:
        raise HTTPException(503, "smart_routing_not_configured")
    try:
        return await services.smart.start_progressive_search(query)
    except ProviderError as error:
        if str(error) == "progressive_search_capacity_exceeded":
            raise HTTPException(429, str(error)) from None
        raise


@router.post("/v1/smart/search-jobs/poll", response_model=ProgressiveSearchState, dependencies=[Depends(authorize)])
async def smart_search_job_poll(query: ProgressiveSearchPoll, *, services: Services = Depends(get_services)):
    state = await services.smart.poll_progressive_search(query.job_id)
    if state is None:
        raise HTTPException(404, "progressive_search_job_not_found")
    return state


@router.post("/v1/smart/search", response_model=SmartResult, dependencies=[Depends(authorize)])
async def smart_search(
    query: SmartSearch,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    if query.calculate_routes and services.smart.demo is None and services.smart.router is None:
        raise HTTPException(503, "smart_routing_not_configured")
    return await operations.run(lambda: services.smart.search(query))


@router.post("/v1/smart/routes", response_model=SmartResult, dependencies=[Depends(authorize)])
async def smart_routes(
    query: SmartRouteRequest,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    if services.smart.demo is None and services.smart.router is None:
        raise HTTPException(503, "smart_routing_not_configured")
    return await operations.run(lambda: services.smart.add_routes(query))


@router.post("/v1/smart/rerank", response_model=SmartResult, dependencies=[Depends(authorize)])
async def smart_rerank(query: SmartRerank, *, services: Services = Depends(get_services)):
    try:
        return await services.smart.rerank(query)
    except ProviderError as error:
        raise HTTPException(409, str(error)) from None
    except ValueError:
        raise HTTPException(422, "invalid_ranking_options_for_snapshot") from None


@router.post("/v1/smart/refresh-prices", response_model=SmartResult, dependencies=[Depends(authorize)])
async def smart_refresh_prices(
    query: SmartPriceRefresh,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    try:
        services.smart.verify(query.snapshot, query.signature)
    except ProviderError as error:
        raise HTTPException(409, str(error)) from None
    return await operations.run(lambda: services.smart.refresh_prices(query))
