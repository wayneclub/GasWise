from fastapi import APIRouter, Depends

from gaswise.api.dependencies import authorize, get_services, get_settings
from gaswise.app.runtime import Services
from gaswise.app.settings import Settings

router = APIRouter()


@router.get("/healthz")
async def health(*, settings: Settings = Depends(get_settings)):
    return {"status": "ok", "mode": settings.mode}


@router.get("/v1/capabilities", dependencies=[Depends(authorize)])
async def capabilities(
    *, services: Services = Depends(get_services), settings: Settings = Depends(get_settings)
):
    return {
        "vehicle_specifications_enabled": settings.vehicle_specifications_enabled,
        "vehicle_specifications_transport": settings.vehicle_specifications_transport,
        "smart_search_enabled": True,
        "smart_routes_enabled": services.smart.demo is not None or services.smart.router is not None,
        "routing_source": "synthetic"
        if settings.mode == "demo"
        else "google_maps_web_directions"
        if settings.maps_web_routes_enabled
        else "google_routes"
        if settings.mode == "google" and settings.google_routes_enabled
        else None,
        "fuel_consumption_model": "distance_fuel_balance_v1",
        "vehicle_catalog_enabled": True,
        "vin_decoder_enabled": True,
        "vin_decoder_source": "nhtsa_vpic",
        "plate_lookup_enabled": services.plate is not None,
        "plate_lookup_source": getattr(services.plate, "source_id", settings.plate_lookup_source)
        if services.plate is not None
        else None,
        "vehicle_fuel_baseline": "epa_combined_mpg",
        "smart_snapshot_lifetime_seconds": 600,
        "top_tier_list_origin": services.top_tier.current().origin if services.top_tier else None,
        "top_tier_list_modified_at": services.top_tier.current().page_modified_at if services.top_tier else None,
        "smart_rerank_upstream_calls": 0,
        "smart_inventory_source": "synthetic"
        if settings.mode == "demo"
        else "google_maps_web"
        if settings.maps_web_session_file
        else "google_places"
        if settings.google_api_key.get_secret_value()
        else None,
        "ranking_unknown_payment_allowed_by_default": False,
        "google_prices_enabled": bool(settings.google_api_key.get_secret_value()),
        "waze_prices_enabled": settings.waze_enabled,
        "waze_transport": "http",
        "waze_auto_login": settings.waze_auto_login,
        "waze_web_login_exchange_verified": False,
        "google_prices_max_results": 20,
        "aaa_regional_averages_enabled": True,
        "aaa_update_frequency": "daily",
        "mode": settings.mode,
        "recommendations_enabled": services.service is not None,
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
