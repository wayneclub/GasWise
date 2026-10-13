"""FastAPI entry point; provider construction lives in the composition root."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gaswise.api import history, locations, parts, quality, recommendations, smart, sources, system, vehicles
from gaswise.api.operations import OperationRunner
from gaswise.app.bootstrap import build_services
from gaswise.app.runtime import ProviderOverrides
from gaswise.app.settings import Settings


def create_app(
    settings: Settings | None = None,
    provider=None,
    vehicle_provider=None,
    vin_provider=None,
    plate_provider=None,
    *,
    service_factory=build_services,
) -> FastAPI:
    settings = settings or Settings()
    overrides = ProviderOverrides(provider, vehicle_provider, vin_provider, plate_provider)

    @asynccontextmanager
    async def lifespan(app):
        async with service_factory(settings, overrides) as services:
            app.state.services = services
            yield

    app = FastAPI(
        title="GasWise API",
        version="0.5.0",
        lifespan=lifespan,
        description="Independent fuel cost API. Decimal money is serialized as strings. Demo is synthetic.",
    )
    app.state.settings = settings

    @app.exception_handler(RequestValidationError)
    async def private_validation_errors(request, error):
        # Pydantic's default errors echo submitted VIN/plate/other request input.
        # Keep structural diagnostics without input, exception context or values.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "type": item["type"],
                        "loc": (*item["loc"][:-1], "extra_field")
                        if item["type"] == "extra_forbidden"
                        else item["loc"],
                        "msg": "Invalid request value",
                    }
                    for item in error.errors()
                ]
            },
            headers={"Cache-Control": "no-store"},
        )

    app.state.operations = OperationRunner(settings.max_concurrent_searches)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for module in (system, history, locations, parts, vehicles, sources, smart, recommendations, quality):
        app.include_router(module.router)

    @app.middleware("http")
    async def prevent_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()
