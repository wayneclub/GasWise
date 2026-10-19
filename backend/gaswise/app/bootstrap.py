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
from gaswise.providers.http.egress_pool import PooledGasBuddySession, PooledHTTPClient
from gaswise.providers.http.parts import PartsHTTP
from gaswise.providers.http.public import PublicHTTP
from gaswise.providers.notifications.telegram import TelegramSender
from gaswise.providers.pricing.aaa import AAAProvider
from gaswise.providers.pricing.aaa_http import AAAHTTP
from gaswise.providers.pricing.demo import DemoComparisonSource, DemoProvider
from gaswise.providers.pricing.feed import HTTPPriceSource
from gaswise.providers.pricing.registry import SourceRegistry
from gaswise.providers.quality.top_tier import TopTierProvider
from gaswise.providers.storage.postgres import PostgresPricingCache
from gaswise.providers.storage.request_budget import RequestBudget
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.providers.vehicles.hertz import HertzProvider
from gaswise.providers.vehicles.plate import AutoZonePlateProvider, PlateProvider
from gaswise.providers.vehicles.specifications import SpecificationProvider
from gaswise.providers.vehicles.vin import VinProvider
from gaswise.providers.waze.provider import WazeProvider
from gaswise.services.parts.fitment import PartsProvider
from gaswise.services.pricing.base_collection import BaseCollection
from gaswise.services.pricing.collection_notifications import CollectionNotifications
from gaswise.services.pricing.hot_refresh import HotQueryRefresh
from gaswise.services.pricing.search import SearchService
from gaswise.services.pricing.shared_cache import SharedPricingCache
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
            proxy = str(settings.gasbuddy_http_proxy) if settings.gasbuddy_http_proxy else None
            factory = (
                (
                    lambda: CurlHTTPClient(
                        allowed_hosts={"www.gasbuddy.com"},
                        preserve_cookies=True,
                        profile="chrome" if settings.gasbuddy_http_client == "curl_chrome" else None,
                        proxy=proxy,
                    )
                )
                if settings.gasbuddy_http_client != "httpx"
                else None
            )
            price_worker = GasBuddyHTTPSession(
                session_seconds=settings.gasbuddy_session_seconds, client_factory=factory, proxy=proxy
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
        if settings.pricing_egress_proxies:
            await price_worker.close()
            price_worker = PooledGasBuddySession(settings.pricing_egress_proxies,
                                                session_seconds=settings.gasbuddy_session_seconds,
                                                health_file=settings.pricing_egress_health_file)
            maps_client = PooledHTTPClient(settings.pricing_egress_proxies, health_file=settings.pricing_egress_health_file)
            waze_client = PooledHTTPClient(settings.pricing_egress_proxies, health_file=settings.pricing_egress_health_file)
            stack.push_async_callback(maps_client.aclose)
            stack.push_async_callback(waze_client.aclose)
        else:
            waze_client = client
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
                waze_client,
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
        shared_cache = None
        if settings.database_url.get_secret_value():
            store = await PostgresPricingCache.connect(settings.database_url.get_secret_value())
            stack.push_async_callback(store.close)
            shared_cache = SharedPricingCache(store, settings.pricing_cache_fresh_seconds)
            stack.push_async_callback(shared_cache.close)
            budget = RequestBudget(store, {
                "gasbuddy": settings.gasbuddy_requests_per_minute,
                "maps": settings.maps_requests_per_minute,
                "waze": settings.waze_requests_per_minute,
            }, background_daily_limit=settings.hot_pricing_refresh_daily_requests)
            await store.configure_background_pacing("gasbuddy", settings.gasbuddy_background_pacing_enabled)
            if settings.pricing_daily_ramp_enabled:
                for source in budget.limits:
                    initial = settings.hot_pricing_refresh_daily_requests
                    if source == "gasbuddy" and settings.gasbuddy_background_daily_requests is not None:
                        initial = settings.gasbuddy_background_daily_requests
                    await store.configure_daily_ramp([source], initial,
                                                     settings.pricing_daily_ramp_floor, settings.pricing_daily_ramp_max)
            else:
                await store.disable_daily_ramp(list(budget.limits))
            price_worker.request_budget = budget
            maps_web.request_budget = budget
            if website_router is not None:
                website_router.request_budget = budget
            if waze is not None:
                waze.request_budget = budget
            cleanup_task = asyncio.create_task(shared_cache.maintain())
            async def stop_cache_cleanup():
                cleanup_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await cleanup_task
            stack.push_async_callback(stop_cache_cleanup)
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
            shared_cache=shared_cache,
        )
        stack.push_async_callback(smart.close)
        if settings.base_collection_enabled:
            if shared_cache is None or settings.mode == "demo":
                raise ValueError("Fixed base collection requires shared PostgreSQL and live mode")
            smart.base_collection = BaseCollection(
                smart, settings.base_collection_bases, interval=settings.base_collection_interval_seconds,
                limits=budget.limits, daily_limit=settings.hot_pricing_refresh_daily_requests,
                egress_lanes=len(settings.pricing_egress_proxies) or 1)
            await smart.base_collection.initialize()
            base_task = asyncio.create_task(smart.base_collection.run())

            async def stop_base_collection():
                base_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await base_task

            stack.push_async_callback(stop_base_collection)
        if settings.collection_telegram_enabled:
            sender = TelegramSender(settings.collection_telegram_bot_token, settings.collection_telegram_chat_id,
                                    settings.collection_telegram_thread_id)
            notifier = CollectionNotifications(store, sender)
            notification_task = asyncio.create_task(notifier.run())

            async def stop_collection_notifications():
                notification_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await notification_task

            stack.push_async_callback(stop_collection_notifications)
        if settings.hot_pricing_refresh_enabled:
            if shared_cache is None or settings.mode == "demo":
                raise ValueError("Hot pricing refresh requires shared PostgreSQL cache and live mode")
            smart.hot_refresh = HotQueryRefresh(
                shared_cache,
                max_queries=settings.hot_pricing_refresh_max_queries,
                interval=max(settings.hot_pricing_refresh_interval_seconds, settings.pricing_cache_fresh_seconds),
                limits=budget.limits,
                daily_limit=settings.hot_pricing_refresh_daily_requests,
            )
            smart.hot_refresh.priority_check = smart.base_collection.pending if smart.base_collection else None
            hot_task = asyncio.create_task(smart.hot_refresh.run())

            async def stop_hot_refresh():
                hot_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await hot_task

            stack.push_async_callback(stop_hot_refresh)
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
