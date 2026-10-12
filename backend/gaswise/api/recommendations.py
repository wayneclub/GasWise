import json
from asyncio import sleep

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from gaswise.api.dependencies import authorize, get_operations, get_services, get_settings
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.app.settings import Settings
from gaswise.contracts.search import Search, SearchResult

router = APIRouter()


async def run_search(query, services: Services, operations: OperationRunner):
    if services.service is None:
        raise HTTPException(503, "routing_provider_not_configured")
    return await operations.run(lambda: services.service.search(query))


@router.post("/v1/recommendations", response_model=SearchResult, dependencies=[Depends(authorize)])
async def recommendations(
    query: Search,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await run_search(query, services, operations)


@router.post(
    "/v1/recommendations/stream",
    dependencies=[Depends(authorize)],
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE snapshot / error events"}},
)
async def stream(
    query: Search,
    request: Request,
    *,
    services: Services = Depends(get_services),
    settings: Settings = Depends(get_settings),
    operations: OperationRunner = Depends(get_operations),
):
    # Validate first snapshot before sending 200 so upstream failures retain HTTP status.
    first = await run_search(query, services, operations)

    async def events():
        yield f"event: snapshot\ndata: {first.model_dump_json()}\n\n"
        # One-hour sessions bound provider spending. Clients reconnect explicitly.
        elapsed = 0
        while elapsed < 3600:
            await sleep(min(15, settings.refresh_seconds - elapsed % settings.refresh_seconds))
            elapsed += min(15, settings.refresh_seconds - elapsed % settings.refresh_seconds)
            if await request.is_disconnected():
                break
            if elapsed % settings.refresh_seconds:
                yield ": keepalive\n\n"
                continue
            try:
                result = await run_search(query, services, operations)
                yield f"event: snapshot\ndata: {result.model_dump_json()}\n\n"
            except HTTPException as error:
                yield (
                    "event: error\ndata: "
                    + json.dumps({"code": error.detail, "status": error.status_code})
                    + "\n\n"
                )
                break
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
