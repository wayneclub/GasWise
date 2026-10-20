from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from gaswise.api.alerts import router
from gaswise.api.dependencies import get_services, get_settings
from gaswise.app.settings import Settings
from gaswise.contracts.alerts import InstallationCreate


@pytest.mark.asyncio
async def test_alert_config_degrades_when_not_configured():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(alerts=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/alerts/config", json={})
        assert response.json() == {"enabled": False, "vapid_public_key": None}
        assert (await client.post("/v1/alerts/installations", json={})).status_code == 422


@pytest.mark.asyncio
async def test_installation_and_need_state_never_accept_extra_private_fields():
    alerts = SimpleNamespace(
        public_key="vapid-public",
        create=AsyncMock(return_value={"installation_id": "i" * 24, "installation_token": "t" * 43}),
        update_need=AsyncMock(),
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(alerts=alerts)
    install = {"subscription": {"endpoint": "https://push.example.test/one",
               "keys": {"p256dh": "p" * 24, "auth": "a" * 12}}, "timezone": "America/Los_Angeles"}
    auth = {"installation_id": "i" * 24, "installation_token": "t" * 43,
            "state": "approaching", "confidence": "medium", "ttl_hours": 48}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/v1/alerts/installations", json=install)).status_code == 200
        assert (await client.post("/v1/alerts/need-state", json=auth)).json() == {"status": "updated"}
        for forbidden in ("odometer", "vin", "route", "latitude", "tank_size"):
            response = await client.post("/v1/alerts/need-state", json={**auth, forbidden: "private"})
            assert response.status_code == 422


def test_push_contract_rejects_private_network_targets_and_fake_timezones():
    base = {"subscription": {"endpoint": "https://push.example.test/one",
            "keys": {"p256dh": "p" * 24, "auth": "a" * 12}}, "timezone": "America/Los_Angeles"}
    assert InstallationCreate.model_validate(base).timezone == "America/Los_Angeles"
    with pytest.raises(ValidationError):
        InstallationCreate.model_validate({**base, "subscription": {**base["subscription"], "endpoint": "https://127.0.0.1/push"}})
    with pytest.raises(ValidationError):
        InstallationCreate.model_validate({**base, "timezone": "Fake/Nowhere"})


def test_smart_alerts_fail_closed_without_every_secret():
    with pytest.raises(ValidationError, match="Smart alerts require"):
        Settings(smart_alerts_enabled=True, database_url="postgresql://example/test")
