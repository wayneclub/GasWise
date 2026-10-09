import asyncio
import json
import secrets
from asyncio import sleep
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from gaswise.brands import BRANDS, SOURCE_URL, VERIFIED_ON
from gaswise.models import (
    GasBuddyBrands,
    GasBuddyPrices,
    GasBuddySearch,
    GooglePrices,
    GooglePriceSearch,
    Search,
    SearchResult,
)
from gaswise.providers.aaa import STATES, AAAProvider, AAASnapshot
from gaswise.providers.base import ProviderError
from gaswise.providers.demo import DemoComparisonSource, DemoProvider
from gaswise.providers.feed import HTTPPriceSource
from gaswise.providers.gasbuddy import GasBuddyFeedProvider
from gaswise.providers.gasbuddy_web import GasBuddyWebProvider
from gaswise.providers.google import GoogleProvider
from gaswise.providers.http_session import GasBuddyHTTPSession
from gaswise.providers.registry import SourceRegistry
from gaswise.service import SearchService
from gaswise.settings import Settings


def create_app(settings: Settings | None = None, provider=None) -> FastAPI:
    settings = settings or Settings()
    slots = asyncio.Semaphore(settings.max_concurrent_searches)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15), limits=httpx.Limits(max_connections=30)
        ) as client:
            app.state.google_prices = (
                GoogleProvider(client, settings.google_api_key.get_secret_value())
                if settings.google_api_key.get_secret_value() else None
            )
            selected = provider or (
                DemoProvider()
                if settings.mode == "demo"
                else GoogleProvider(client, settings.google_api_key.get_secret_value())
                if settings.mode == "google"
                else None
            )
            if settings.gasbuddy_web_transport == "http":
                price_worker = GasBuddyHTTPSession(session_seconds=settings.gasbuddy_session_seconds)
            else:
                # Browser transports are optional. The default HTTP service never imports Playwright.
                from gaswise.providers.anonymous_session import GasBuddyAnonymousSession
                from gaswise.providers.browser_worker import GasBuddyBrowserWorker

                worker_class = (
                    GasBuddyAnonymousSession
                    if settings.gasbuddy_web_transport == "session_http"
                    else GasBuddyBrowserWorker
                )
                worker_args = (
                    {"session_seconds": settings.gasbuddy_session_seconds}
                    if settings.gasbuddy_web_transport == "session_http"
                    else {}
                )
                price_worker = worker_class(
                    settings.gasbuddy_browser_channel,
                    settings.gasbuddy_browser_timeout_seconds,
                    settings.gasbuddy_browser_headless,
                    **worker_args,
                )
            loader = price_worker.snapshot
            web = GasBuddyWebProvider(
                client,
                locator=selected if settings.mode == "google" else None,
                snapshot_loader=loader,
                transport=settings.gasbuddy_web_transport,
            )
            app.state.aaa = AAAProvider(client)
            app.state.gasbuddy_web = web
            registry = SourceRegistry()
            if settings.mode == "demo":
                registry.register("synthetic", selected)
                registry.register("gasbuddy_demo", DemoComparisonSource())
            else:
                if settings.mode == "google":
                    registry.register("google_places", selected)
                if settings.gasbuddy_web_enabled and settings.mode == "google":
                    registry.register("gasbuddy_web", web, 45)
                elif settings.gasbuddy_web_enabled:
                    registry.disabled(
                        "gasbuddy_web",
                        "raw quotes available at /v1/sources/gasbuddy/prices; station locator required for normalized coordinates",
                    )
                if settings.gasbuddy_feed_url:
                    registry.register(
                        "gasbuddy",
                        GasBuddyFeedProvider(
                            client,
                            str(settings.gasbuddy_feed_url),
                            settings.gasbuddy_feed_token.get_secret_value(),
                        ),
                    )
                for config in settings.price_sources:
                    if config.enabled:
                        registry.register(
                            config.source_id,
                            HTTPPriceSource(
                                client,
                                config.source_id,
                                str(config.url),
                                config.token.get_secret_value(),
                                config.timeout_seconds,
                            ),
                            config.timeout_seconds,
                        )
                    else:
                        registry.disabled(config.source_id)
            app.state.source_registry = registry
            app.state.price_provider = registry.provider()
            if provider is None and settings.mode != "prices_only":
                selected = registry.provider(selected)
            app.state.service = (
                SearchService(selected, settings.mode) if settings.mode != "prices_only" else None
            )
            try:
                yield
            finally:
                await price_worker.close()

    app = FastAPI(
        title="GasWise API",
        version="0.5.0",
        lifespan=lifespan,
        description="Independent fuel cost API. Decimal money is serialized as strings. Demo is synthetic.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    bearer = HTTPBearer(auto_error=False)

    async def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        supplied = credentials.credentials if credentials else ""
        token = settings.api_token.get_secret_value()
        if token and not secrets.compare_digest(supplied, token):
            raise HTTPException(401, "invalid_api_token")

    async def run_operation(operation):
        try:
            await asyncio.wait_for(slots.acquire(), timeout=0.05)
        except TimeoutError:
            raise HTTPException(429, "search_capacity_exceeded", headers={"Retry-After": "5"}) from None
        try:
            async with asyncio.timeout(55):
                return await operation()
        except ProviderError as error:
            raise HTTPException(502, str(error)) from None
        except TimeoutError:
            raise HTTPException(504, "search_timeout") from None
        finally:
            slots.release()

    async def run_search(query):
        if app.state.service is None:
            raise HTTPException(503, "routing_provider_not_configured")
        return await run_operation(lambda: app.state.service.search(query))

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "mode": settings.mode}

    @app.get("/v1/capabilities", dependencies=[Depends(authorize)])
    async def capabilities():
        return {
            "google_prices_enabled": bool(settings.google_api_key.get_secret_value()),
            "google_prices_max_results": 20,
            "aaa_regional_averages_enabled": True,
            "aaa_update_frequency": "daily",
            "mode": settings.mode,
            "recommendations_enabled": settings.mode != "prices_only",
            "refresh_seconds": settings.refresh_seconds,
            "currency": "USD",
            "volume_unit": "US_gallon",
            "distance_unit": "mile",
            "octane_verified": settings.mode == "demo",
            "historical_storage": False,
            "ranking_model": "deterministic-multisource-v2",
            "price_confidence_model": "freshness_purchase_conditions_source_agreement_rules",
            "gasbuddy_web_enabled": settings.gasbuddy_web_enabled,
            "gasbuddy_web_transport": settings.gasbuddy_web_transport,
            "gasbuddy_browser_headless": settings.gasbuddy_browser_headless,
            "gasbuddy_session_seconds": settings.gasbuddy_session_seconds,
            "gasbuddy_requires_browser": settings.gasbuddy_web_transport != "http",
            "gasbuddy_licensed_feed_configured": settings.gasbuddy_feed_url is not None,
            "gasbuddy_public_api_verified": False,
            "route_search_scope": "origin_radius",
            "max_candidates": 30,
        }

    @app.get("/v1/sources", dependencies=[Depends(authorize)])
    async def price_sources():
        return {
            "sources": app.state.source_registry.describe(),
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

    @app.get("/v1/sources/aaa/averages", response_model=AAASnapshot, dependencies=[Depends(authorize)])
    async def aaa_averages(state: str = Query(default="CA", min_length=2, max_length=2)):
        state = state.upper()
        if state not in STATES:
            raise HTTPException(422, "invalid_us_state")
        return await run_operation(lambda: app.state.aaa.averages(state))

    @app.post("/v1/prices", dependencies=[Depends(authorize)])
    async def prices(query: Search):
        snapshot = await run_operation(lambda: app.state.price_provider.snapshot(query))
        return {"stations": snapshot.stations, "source_statuses": snapshot.statuses}

    @app.post("/v1/sources/google/prices", response_model=GooglePrices, dependencies=[Depends(authorize)])
    async def google_prices(query: GooglePriceSearch):
        if app.state.google_prices is None:
            raise HTTPException(503, "google_places_not_configured")
        stations = await run_operation(lambda: app.state.google_prices.stations(query))
        return GooglePrices(stations=stations)

    @app.get("/v1/sources/gasbuddy/brands", response_model=GasBuddyBrands, dependencies=[Depends(authorize)])
    async def gasbuddy_brands():
        return GasBuddyBrands(verified_on=VERIFIED_ON, source_url=SOURCE_URL, brands=BRANDS)

    @app.post("/v1/sources/gasbuddy/prices", response_model=GasBuddyPrices, dependencies=[Depends(authorize)])
    async def gasbuddy_prices(query: GasBuddySearch):
        if not settings.gasbuddy_web_enabled:
            raise HTTPException(503, "gasbuddy_web_not_enabled")
        return await run_operation(lambda: app.state.gasbuddy_web.prices(query))

    @app.post("/v1/recommendations", response_model=SearchResult, dependencies=[Depends(authorize)])
    async def recommendations(query: Search):
        return await run_search(query)

    @app.post(
        "/v1/recommendations/stream",
        dependencies=[Depends(authorize)],
        responses={200: {"content": {"text/event-stream": {}}, "description": "SSE snapshot / error events"}},
    )
    async def stream(query: Search, request: Request):
        # Validate first snapshot before sending 200 so upstream failures retain HTTP status.
        first = await run_search(query)

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
                    result = await run_search(query)
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

    @app.middleware("http")
    async def prevent_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()
