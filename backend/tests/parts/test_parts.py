import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gaswise.app.settings import Settings
from gaswise.contracts.parts import PartsRequest
from gaswise.main import create_app
from gaswise.services.parts.fitment import ApplicationParser, PartsProvider, assess_applications
from tests.support.parts import (
    ROW as ROW,
)
from tests.support.parts import (
    URL as URL,
)
from tests.support.parts import (
    Decoder as Decoder,
)
from tests.support.parts import (
    amazon_html as amazon_html,
)
from tests.support.parts import (
    catalog_html as catalog_html,
)
from tests.support.parts import (
    decoded as decoded,
)
from tests.support.vin import VIN


@pytest.mark.parametrize(
    "url",
    [
        "http://www.amazon.com/dp/B019IPTB0W",
        "https://amazon.com.evil.com/dp/B019IPTB0W",
        "https://www.amazon.com:8000/dp/B019IPTB0W",
        "https://user@amazon.com/dp/B019IPTB0W",
        "https://127.0.0.1/dp/B019IPTB0W",
        "https://amzn.to/test",
    ],
)
def test_url_boundary(url):
    with pytest.raises(ValidationError):
        PartsRequest(amazon_url=url, vin={"vin": VIN})


def test_identity_required_and_tracking_removed():
    assert PartsRequest(amazon_url=URL, vin={"vin": VIN}).amazon_url == "https://www.amazon.com/dp/B019IPTB0W"
    for extra in ({}, {"vin": {"vin": VIN}, "plate": {"plate": "TEST", "state": "CA"}}):
        with pytest.raises(ValidationError):
            PartsRequest(amazon_url=URL, **extra)


def test_displacement_does_not_prove_engine_or_drivetrain():
    status, rows, _ = assess_applications(decoded(), [ROW])
    assert status == "needs_confirmation" and rows == [ROW]
    assert assess_applications(decoded(engine_model="M276.823"), [ROW])[0] == "needs_confirmation"
    assert (
        assess_applications(decoded(engine_model="M276.823", drive="AWD/All-Wheel Drive"), [ROW])[0]
        == "compatible"
    )
    assert (
        assess_applications(decoded(engine_model="M276.850", drive="AWD"), [ROW])[0] == "needs_confirmation"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"ccm": "3498"},
        {"vehicleMake": "BMW"},
        {"vehicleName": "E450"},
        {"serialNumberRange": "up to 12345"},
        {"vehicleManufacturedFrom": "2018-06-01"},
    ],
)
def test_mismatch_or_restriction_never_confirmed(change):
    assert (
        assess_applications(decoded(engine_model="M276.823", drive="AWD"), [{**ROW, **change}])[0]
        == "needs_confirmation"
    )


async def test_provider_verified_product_and_catalog():
    calls = []

    def handle(request):
        calls.append(request)
        assert not any(k in request.headers for k in ("cookie", "authorization", "x-api-key"))
        body = amazon_html() if request.url.host == "www.amazon.com" else catalog_html()
        return httpx.Response(200, text=body)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), cookies={"secret": "private"}, auth=("secret", "secret")
    ) as client:
        result = await PartsProvider(client).resolve(
            PartsRequest(amazon_url=URL, vin={"vin": VIN}), Decoder(), None
        )
    assert result.status == "compatible" and result.product_status == "identified"
    assert len(calls) == 2 and len(result.applications) == 1
    assert VIN not in result.model_dump_json()


async def test_blocked_amazon_and_user_hint_are_not_verified():
    def handle(request):
        return httpx.Response(
            200, text=catalog_html() if request.url.host == "www.mann-filter.com" else "Robot Check"
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = PartsProvider(client)
        query = PartsRequest(amazon_url=URL, vin={"vin": VIN})
        result = await provider.resolve(query, Decoder(), None)
        assert result.product_status == "unavailable" and result.status == "needs_confirmation"
        query.brand, query.part_number = "MANN-FILTER", "HU 7025 z"
        result = await provider.resolve(query, Decoder(), None)
        assert result.status == "needs_confirmation" and result.applications
        assert result.product_status == "user_supplied_unverified"


async def test_redirect_not_followed():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://localhost/private"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        assert await PartsProvider(client).public_html("https://www.amazon.com/dp/B019IPTB0W") is None
    assert len(calls) == 1


def test_endpoint_wiring(monkeypatch):
    async def resolve(self, query, decoder, plate):
        from gaswise.contracts.parts import PartsResult

        return PartsResult(
            status="needs_confirmation",
            amazon_url=query.amazon_url,
            product_status="unavailable",
            vehicle=decoded(),
        )

    monkeypatch.setattr(PartsProvider, "resolve", resolve)
    settings = Settings(
        _env_file=None, mode="demo", gasbuddy_web_enabled=False, waze_enabled=False, api_token=""
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/parts/fitment", json={"amazon_url": URL, "vin": {"vin": VIN}})
    assert response.status_code == 200 and response.json()["status"] == "needs_confirmation"


def test_real_structured_row_parser():
    parser = ApplicationParser()
    parser.feed(catalog_html() * 2)
    assert parser.rows == [ROW]


async def test_conflicting_hint_and_multiple_title_numbers_are_unconfirmed():
    for title, expected in [
        ("Mann Filter HU 7025 z oil filter", "conflict"),
        ("Mann Filter HU 7025 z or HU 6028 z oil filter", "user_supplied_unverified"),
    ]:

        def handle(request):
            return httpx.Response(
                200,
                text=(
                    amazon_html()
                    if expected == "conflict"
                    else '<span id="productTitle">' + title + "</span>"
                )
                if request.url.host == "www.amazon.com"
                else catalog_html(),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            query = PartsRequest(
                amazon_url=URL, vin={"vin": VIN}, brand="MANN-FILTER", part_number="HU 6028 z"
            )
            result = await PartsProvider(client).resolve(query, Decoder(), None)
        assert (
            result.status == ("conflict" if expected == "conflict" else "needs_confirmation")
            and result.product_status == expected
        )


def test_missing_chassis_and_decode_errors_prevent_confirmation():
    vehicle = decoded(engine_model="M276.823", drive="AWD")
    vehicle.series = None
    assert assess_applications(vehicle, [ROW])[0] == "needs_confirmation"
    vehicle.series = "C238"
    vehicle.error_codes = ["7"]
    assert assess_applications(vehicle, [ROW])[0] == "needs_confirmation"
