import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.main import create_app
from gaswise.providers.http.public import PublicHTTP
from gaswise.providers.vehicles.specifications import SpecificationProvider, parse_specs
from tests.support.specification_assessment import EPA, HERTZ, HERTZ_URL


class FakeResponse:
    status_code = 200
    closed = False
    chunks = [b"public data"]

    async def aiter_content(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


async def test_anonymous_fresh_session_no_cookie_reuse_or_redirects():
    sessions = []

    class Session:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.response = FakeResponse()
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            assert kwargs["auth"] is None and kwargs["cookies"] == {}
            assert kwargs["discard_cookies"] is True and kwargs["allow_redirects"] is False
            assert kwargs["stream"] is True and kwargs.get("headers") is None
            return self.response

    provider = PublicHTTP(Session)
    for _ in range(2):
        assert await provider.read("https://www.hertzcarsales.com/used-cars-for-sale.htm") == "public data"
    assert len(sessions) == 2 and all(s.response.closed for s in sessions)
    assert all(s.options["impersonate"] == "chrome" and s.options["trust_env"] is False for s in sessions)
    sessions.clear()
    FakeResponse.chunks = [b"a" * 5, b"b" * 5]
    try:
        assert await provider.read("https://www.edmunds.com/", max_bytes=8) is None
        assert sessions[0].response.closed
    finally:
        FakeResponse.chunks = [b"public data"]


async def test_fixed_hosts_only():
    for url in [
        "http://www.edmunds.com/",
        "https://www.edmunds.com.evil.test/",
        "https://user@www.edmunds.com/",
        "https://localhost/",
    ]:
        with pytest.raises(ValueError):
            await PublicHTTP().read(url)


class PublicFixture:
    def __init__(self, inventory=None):
        self.calls = []
        self.inventory = (
            inventory
            if inventory is not None
            else [{"link": HERTZ_URL, "year": 2021, "make": "Toyota", "model": "Camry"}]
        )

    async def read(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "edmunds.com" in url:
            return '<script src="/edge-check.js"></script>'
        if "getInventoryAndFacets" in url:
            body = kwargs["json_body"]
            assert body["inventoryParameters"] == {"make": ["Toyota"], "model": ["Camry"], "year": ["2021"]}
            return json.dumps({"inventory": self.inventory})
        return HERTZ


async def test_public_json_inventory_and_one_detail_yield_agreement():
    public = PublicFixture()
    async with httpx.AsyncClient() as client:
        provider = SpecificationProvider(client, public)
        rows = await provider.observations(EPA[43305])
        assert [r.status for r in rows] == ["unavailable", "matched"]
        assert rows[1].fuel_grade == "regular"
        assert len(public.calls) == 3
        await provider.observations(EPA[43305])
        assert len(public.calls) == 3


@pytest.mark.parametrize(
    "row",
    [
        {
            "link": "https://evil.example/used/Foo/2021-Camry.htm",
            "year": 2021,
            "make": "Toyota",
            "model": "Camry",
        },
        {"link": HERTZ_URL, "year": 2020, "make": "Toyota", "model": "Camry"},
    ],
)
async def test_inventory_host_and_identity_mismatch_do_not_fetch_detail(row):
    public = PublicFixture([row])
    async with httpx.AsyncClient() as client:
        result = await SpecificationProvider(client, public).hertz(EPA[43305])
    assert result.status == "unavailable" and len(public.calls) == 1


def test_non_spec_equipment_rows_do_not_hide_powertrain():
    # Full live DDC equipment includes category rows without a spec object.
    html = HERTZ.replace('"specification":[', '"specification":[{"category":"Powertrain"},{"spec":null},')
    assert parse_specs(html, EPA[43305], "hertz", HERTZ_URL).status == "matched"
    assert parse_specs(html, EPA[43302], "hertz", HERTZ_URL).status == "mismatch"


def test_main_transport_wiring_and_fuel_consensus(monkeypatch):
    public = PublicFixture()
    monkeypatch.setattr("gaswise.app.bootstrap.PublicHTTP", lambda: public)
    from tests.support.specification_assessment import raw_profile

    original_client = httpx.AsyncClient

    def handle(request):
        assert request.url.host == "www.fueleconomy.gov"
        return httpx.Response(200, json=raw_profile(EPA[43305]))

    monkeypatch.setattr(
        "gaswise.app.bootstrap.httpx.AsyncClient",
        lambda *a, **kw: original_client(transport=httpx.MockTransport(handle)),
    )
    settings = Settings(
        _env_file=None, vehicle_specifications_enabled=True, vehicle_specifications_transport="curl"
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/vehicles/fuel-assessment", json={"vehicle_id": 43305})
    assert response.status_code == 200
    assert response.json()["hertz_status"] == "matched"
    assert response.json()["vehicle"]["fuel_recommendation"]["assessment_status"] == "agreement"
