import asyncio
import contextlib
import secrets
from contextlib import AsyncExitStack, asynccontextmanager

import httpx

from gaswise.app.runtime import ProviderOverrides, Services
from gaswise.app.settings import Settings
from gaswise.providers.gasbuddy.feed import GasBuddyFeedProvider
from gaswise.providers.gasbuddy.http_session import GasBuddyHTTPSession
from gaswise.providers.gasbuddy.web import GasBuddyWebProvider
from gaswise.providers.geocoding import LocationProvider
from gaswise.providers.google.maps_web import MapsWebProvider
from gaswise.providers.google.places import GoogleProvider
from gaswise.providers.google.routes import MapsWebRouteProvider
from gaswise.providers.http.curl_client import CurlHTTPClient
from gaswise.providers.http.parts import PartsHTTP
from gaswise.providers.http.public import PublicHTTP
from gaswise.providers.pricing.aaa import AAAProvider
from gaswise.providers.pricing.aaa_http import AAAHTTP
from gaswise.providers.pricing.demo import DemoComparisonSource, DemoProvider
from gaswise.providers.pricing.feed import HTTPPriceSource
from gaswise.providers.pricing.registry import SourceRegistry
from gaswise.providers.quality.top_tier import TopTierProvider
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.providers.vehicles.hertz import HertzProvider
from gaswise.providers.vehicles.plate import AutoZonePlateProvider, PlateProvider
from gaswise.providers.vehicles.specifications import SpecificationProvider
from gaswise.providers.vehicles.vin import VinProvider
from gaswise.providers.waze.provider import WazeProvider
from gaswise.services.parts.fitment import PartsProvider
from gaswise.services.pricing.search import SearchService
from gaswise.services.pricing.smart import SmartService


@asynccontextmanager
async def build_services(settings: Settings, overrides: ProviderOverrides):
    """Composition root: own transports, adapters and application services."""
    provider, vehicle_provider = overrides.provider, overrides.vehicles
    vin_provider, plate_provider = overrides.vin, overrides.plate
    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(
            httpx.AsyncClient(timeout=httpx.Timeout(15), limits=httpx.Limits(max_connections=30))
        )
        maps_client = await stack.enter_async_context(httpx.AsyncClient(timeout=httpx.Timeout(15)))
        top_tier = TopTierProvider(client, settings.top_tier_cache_file, settings.top_tier_refresh_hours)
        if settings.top_tier_refresh_enabled:
            refresher = asyncio.create_task(top_tier.run())

            async def stop_refresher():
                refresher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await refresher

            stack.push_async_callback(stop_refresher)
        public_specs = PublicHTTP() if settings.vehicle_specifications_transport == "curl" else None
        vehicles = vehicle_provider or VehicleProvider(
            client,
            SpecificationProvider(client, public_specs) if settings.vehicle_specifications_enabled else None,
        )
        vin = vin_provider or VinProvider(client)
        hertz = HertzProvider(client, public_specs)
        parts = PartsProvider(
            client,
            PartsHTTP() if settings.parts_http_transport == "curl" else None,
            retailers_enabled=settings.parts_sources_enabled,
        )
        plate = plate_provider or (
            (
                AutoZonePlateProvider(client)
                if settings.plate_lookup_source == "autozone"
                else PlateProvider(client, settings.vehicle_databases_api_key.get_secret_value())
            )
            if settings.plate_lookup_enabled
            else None
        )
        google_prices = (
            GoogleProvider(client, settings.google_api_key.get_secret_value())
            if settings.google_api_key.get_secret_value()
            else None
        )
        selected = provider or (
            DemoProvider()
            if settings.mode == "demo"
            else GoogleProvider(client, settings.google_api_key.get_secret_value())
            if settings.mode == "google"
            else None
        )
        if settings.gasbuddy_web_transport == "http":
            factory = (
                (
                    lambda: CurlHTTPClient(
                        allowed_hosts={"www.gasbuddy.com"},
                        preserve_cookies=True,
                        profile="chrome" if settings.gasbuddy_http_client == "curl_chrome" else None,
                    )
                )
                if settings.gasbuddy_http_client != "httpx"
                else None
            )
            price_worker = GasBuddyHTTPSession(
                session_seconds=settings.gasbuddy_session_seconds, client_factory=factory
            )
        else:
            # Browser transports are optional. The default HTTP service never imports Playwright.
            from gaswise.providers.gasbuddy.anonymous_session import GasBuddyAnonymousSession
            from gaswise.providers.gasbuddy.browser_worker import GasBuddyBrowserWorker

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
        stack.push_async_callback(price_worker.close)
        loader = price_worker.snapshot
        web = GasBuddyWebProvider(
            client,
            locator=selected if settings.mode == "google" else None,
            snapshot_loader=loader,
            transport=settings.gasbuddy_web_transport,
        )
        aaa = AAAProvider(AAAHTTP())
        maps_web = MapsWebProvider(maps_client, settings.maps_web_session_file)
        waze = (
            WazeProvider(
                client,
                settings.waze_session_file,
                settings.waze_login_file,
                settings.waze_auto_login,
            )
            if settings.waze_enabled
            else None
        )
        gasbuddy_web = web
        registry = SourceRegistry()
        if settings.mode == "demo":
            registry.register("synthetic", selected)
            registry.register("gasbuddy_demo", DemoComparisonSource())
        else:
            if settings.maps_web_session_file:
                registry.register("google_maps_web", maps_web)
            if waze is not None:
                registry.register("waze", waze, 50)
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
        source_registry = registry
        price_provider = registry.provider()
        if provider is None and settings.mode != "prices_only":
            selected = registry.provider(selected)
        website_router = (
            MapsWebRouteProvider(maps_client, maps_web) if settings.maps_web_routes_enabled else None
        )
        live_router = website_router or (
            selected if settings.mode == "google" and settings.google_routes_enabled else None
        )
        service = (
            SearchService(selected, settings.mode, vehicles=vehicles, top_tier=top_tier)
            if settings.mode == "demo"
            else (
                SearchService(
                    registry.provider(live_router), settings.mode, vehicles=vehicles, top_tier=top_tier
                )
                if live_router
                else None
            )
        )
        smart = SmartService(
            secrets.token_bytes(32),
            settings.mode,
            gasbuddy=web if settings.gasbuddy_web_enabled else None,
            google=google_prices,
            waze=waze,
            maps_web=maps_web if settings.maps_web_session_file and settings.mode != "demo" else None,
            router=live_router,
            demo=provider or DemoProvider() if settings.mode == "demo" else None,
            vehicles=vehicles,
            top_tier=top_tier,
            aaa=aaa,
        )
        stack.push_async_callback(smart.close)
        yield Services(
            vehicles=vehicles,
            vin=vin,
            hertz=hertz,
            parts=parts,
            plate=plate,
            google_prices=google_prices,
            locations=LocationProvider(maps_web),
            aaa=aaa,
            maps_web=maps_web,
            waze=waze,
            gasbuddy_web=gasbuddy_web,
            source_registry=source_registry,
            price_provider=price_provider,
            service=service,
            smart=smart,
            top_tier=top_tier,
        )
