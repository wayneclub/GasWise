"""Regression checks for extension boundaries and runtime ownership."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gaswise.api.dependencies import get_services
from gaswise.api.operations import OperationRunner
from gaswise.app.bootstrap import build_services
from gaswise.app.runtime import ProviderOverrides
from gaswise.app.settings import Settings
from gaswise.contracts.common import Point, SourceStatus
from gaswise.contracts.search import Search
from gaswise.domain.ports import PriceSnapshot, ProviderError
from gaswise.main import create_app
from gaswise.services.pricing.collection import collect_prices


@pytest.mark.parametrize("failure, status", [(ProviderError("unavailable"), 502), (TimeoutError(), 504)])
async def test_operation_failure_releases_capacity(failure, status):
    runner = OperationRunner(1)

    async def fail():
        raise failure

    with pytest.raises(HTTPException) as caught:
        await runner.run(fail)
    assert caught.value.status_code == status

    async def success():
        return "recovered"

    assert await runner.run(success) == "recovered"


async def test_capacity_rejection_and_cancellation_recover():
    runner = OperationRunner(1, acquire_timeout=0.001)
    started = asyncio.Event()

    async def wait():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(runner.run(wait))
    await started.wait()
    with pytest.raises(HTTPException) as caught:
        await runner.run(wait)
    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "5"}
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async def success():
        return True

    assert await runner.run(success)


async def test_operation_deadline_cancels_upstream_and_recovers():
    runner = OperationRunner(1, timeout=0.001)
    cancelled = asyncio.Event()

    async def wait():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with pytest.raises(HTTPException) as caught:
        await runner.run(wait)
    assert caught.value.status_code == 504
    assert cancelled.is_set()
    assert runner.slots.locked() is False


async def test_custom_snapshot_adapter_preserves_status_without_concrete_inheritance():
    status = SourceStatus(source="custom", status="unavailable", detail="temporarily_unavailable")

    class CustomSource:
        async def snapshot(self, query):
            return PriceSnapshot([], [status])

        async def stations(self, query):
            pytest.fail("snapshot capability must preserve source status")

    result = await collect_prices(CustomSource(), Search(origin=Point(lat=34, lng=-118)))
    assert result.statuses == [status]


def test_service_factory_can_replace_runtime_without_creating_upstream_resources():
    events = []

    class Runtime:
        class Catalog:
            async def menu(self, kind):
                return {"items": [{"text": "2021", "value": "2021"}]}

        vehicles = Catalog()

    @asynccontextmanager
    async def factory(settings, overrides):
        events.append("opened")
        try:
            yield Runtime()
        finally:
            events.append("closed")

    with TestClient(create_app(Settings(), service_factory=factory)) as api:
        response = api.get("/v1/vehicles/years")
        assert response.status_code == 200
        assert response.json()["items"][0]["value"] == "2021"
        assert response.headers["cache-control"] == "no-store"
    assert events == ["opened", "closed"]


def test_dependency_override_and_auth_work_across_domain_routers():
    app = create_app(Settings(api_token="test"))

    class Runtime:
        class Catalog:
            async def menu(self, kind):
                return {"items": []}

        vehicles = Catalog()

    app.dependency_overrides[get_services] = lambda: Runtime()
    with TestClient(app) as api:
        assert api.get("/v1/vehicles/years").status_code == 401
        assert api.get("/v1/sources").status_code == 401
        assert api.post("/v1/parts/fitment", json={}).status_code == 401
        assert api.get("/v1/vehicles/years", headers={"Authorization": "Bearer test"}).status_code == 200


async def test_partial_startup_failure_closes_worker_and_both_clients(monkeypatch):
    import gaswise.app.bootstrap as bootstrap

    events = []

    class Client:
        async def __aenter__(self):
            events.append("client_open")
            return self

        async def __aexit__(self, *args):
            events.append("client_close")

    class Worker:
        def __init__(self, **kwargs):
            pass

        async def snapshot(self, *args):
            pass

        async def close(self):
            events.append("worker_close")

    def fail(*args, **kwargs):
        raise RuntimeError("startup_failed")

    monkeypatch.setattr(bootstrap.httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr(bootstrap, "GasBuddyHTTPSession", Worker)
    monkeypatch.setattr(bootstrap, "GasBuddyWebProvider", fail)
    with pytest.raises(RuntimeError, match="startup_failed"):
        async with build_services(Settings(), ProviderOverrides()):
            pytest.fail("startup must fail before yielding services")
    assert events == ["client_open", "client_open", "worker_close", "client_close", "client_close"]
