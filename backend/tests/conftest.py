"""Local live credentials/configuration must not change automated test behavior."""

import pytest


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for key, value in {
        "GASWISE_MODE": "demo",
        "GASWISE_PARTS_SOURCES_ENABLED": "false",
        "GASWISE_PARTS_HTTP_TRANSPORT": "httpx",
        "GASWISE_GASBUDDY_WEB_ENABLED": "false",
        "GASWISE_API_TOKEN": "",
        "GASWISE_GOOGLE_API_KEY": "",
        "GASWISE_MAPS_WEB_SESSION_FILE": "",
        "GASWISE_WAZE_ENABLED": "false",
        "GASWISE_MAPS_WEB_ROUTES_ENABLED": "false",
        "GASWISE_PLATE_LOOKUP_ENABLED": "false",
        "GASWISE_VEHICLE_DATABASES_API_KEY": "",
        "GASWISE_VEHICLE_SPECIFICATIONS_ENABLED": "false",
        "GASWISE_VEHICLE_SPECIFICATIONS_TRANSPORT": "httpx",
        "GASWISE_TOP_TIER_REFRESH_ENABLED": "false",
        "GASWISE_TOP_TIER_CACHE_FILE": "",
    }.items():
        monkeypatch.setenv(key, value)
