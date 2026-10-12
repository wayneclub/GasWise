from fastapi import APIRouter, Depends

from gaswise.api.dependencies import authorize, get_operations, get_services
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.contracts.parts import PartsRequest, PartsResult, PartsSearchRequest, PartsSearchResult

router = APIRouter()


@router.post("/v1/parts/fitment", response_model=PartsResult, dependencies=[Depends(authorize)])
async def parts_fitment(
    query: PartsRequest,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: services.parts.resolve(query, services.vin, services.plate))


@router.post("/v1/parts/search", response_model=PartsSearchResult, dependencies=[Depends(authorize)])
async def parts_search(query: PartsSearchRequest, *, services: Services = Depends(get_services), operations: OperationRunner = Depends(get_operations)):
    from gaswise.services.parts.search import search_parts
    return await operations.run(lambda: search_parts(query, services.parts, services.vin, services.plate))
