import base64
import json
import struct

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.contracts.sources import GooglePriceSearch
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.waze.protocol import decode, message, number
from gaswise.providers.waze.provider import WazeProvider

QUERY = GooglePriceSearch(origin=Point(lat=34.0833736, lng=-118.3008564))


def envelope(command, data):
    return message(1001, message(command, data))


def fuel_response():
    # Fields/value types observed in the real Melrose 76 response.
    location = number_tag_double(300, -118.3008564) + number_tag_double(301, 34.0833736)
    product = message(1, b"gas_premium") + number(2, 1791527065000)
    product += message(3, b"RedBoogs") + number_tag_float(4, 6.599)
    venue = (
        b"".join(
            message(k, v.encode())
            for k, v in {
                104: "76",
                113: "4600",
                114: "Melrose Ave",
                115: "Los Angeles",
                117: "US",
                119: "90029",
                149: "$",
                152: "venues.158400853.1584008528.5847665",
            }.items()
        )
        + message(109, location)
        + message(150, product)
    )
    return envelope(2742, message(1, message(1, venue)))


def number_tag_double(field, value):
    from gaswise.providers.waze.protocol import varint

    return varint((field << 3) | 1) + struct.pack("<d", value)


def number_tag_float(field, value):
    from gaswise.providers.waze.protocol import varint

    return varint((field << 3) | 5) + struct.pack("<f", value)


def provider(tmp_path, handler, auto_login=True, uid="expired-private-uid"):
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"uid": uid}))
    login = tmp_path / "login.bin"
    login.write_bytes(b"private-login-credential")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WazeProvider(client, session, login, auto_login)


def response(body):
    return httpx.Response(200, content=body, headers={"content-type": "application/x-protobuf"})


async def test_expired_session_refreshes_once_and_normalizes(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/login"):
            assert "uid" not in request.headers and "cookie" not in request.headers
            return response(envelope(2745, message(1, number(1, 42) + message(3, b"new-secret"))))
        if request.headers["uid"] == "expired-private-uid":
            return response(envelope(2003, message(10102, b"Client should relogin to continue working.")))
        assert "cookie" not in request.headers
        body = decode(base64.b64decode(request.content.split(b",", 1)[1]))
        search = decode(decode(body[1001][0])[2741][0])
        assert decode(search[1][0]).get(2)  # Explicit coordinates, not App session location.
        return response(fuel_response())

    source = provider(tmp_path, handler)
    async with source.client:
        rows = await source.stations(QUERY)
    assert calls == ["/rtserver/distrib/command", "/rtserver/distrib/login", "/rtserver/distrib/command"]
    assert len(rows) == 1 and str(rows[0].price_per_gallon) == "6.599"
    assert rows[0].source == "waze" and rows[0].payment_type == "unknown" and rows[0].octane is None
    assert rows[0].price_updated_at.isoformat() == "2026-10-09T06:24:25+00:00"
    assert rows[0].open_now is rows[0].details["open_now"]
    assert source.session_file.stat().st_mode & 0o777 == 0o600


async def test_login_rate_limit_blocks_further_requests(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/login"):
            error = number(2, 2) + message(5, number(1, 6))
            return response(envelope(2745, message(2, error)))
        return response(envelope(2003, message(10102, b"Client should relogin")))

    source = provider(tmp_path, handler)
    async with source.client:
        for _ in range(2):
            with pytest.raises(ProviderError, match="^waze_rate_limited$"):
                await source.prices(QUERY)
    assert len(calls) == 2


async def test_disabled_refresh_and_unknown_error_do_not_leak_or_retry(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return response(envelope(2003, message(10102, b"private-account-detail")))

    source = provider(tmp_path, handler, auto_login=False)
    async with source.client:
        with pytest.raises(ProviderError, match="^waze_upstream_rejected_request$"):
            await source.prices(QUERY)
    assert len(calls) == 1


async def test_postal_filter_and_wrong_fuel_are_not_mislabeled(tmp_path):
    source = provider(tmp_path, lambda request: response(fuel_response()))
    async with source.client:
        assert await source.prices(QUERY.model_copy(update={"postal_code": "90038"})) == []
        assert await source.stations(Search(origin=QUERY.origin, fuel_type="regular")) == []


def test_waze_config_requires_protected_live_mode_and_is_reserved():
    with pytest.raises(ValueError):
        Settings(mode="demo", waze_enabled=True, api_token="test")
    with pytest.raises(ValueError):
        Settings(mode="prices_only", waze_enabled=True, api_token="")
    assert Settings(mode="prices_only", waze_enabled=True, api_token="test").waze_enabled


def test_endpoint_disabled_and_auth_enforced():
    with TestClient(create_app(Settings(mode="demo", api_token="test"))) as client:
        body = {"origin": {"lat": 34, "lng": -118}}
        assert client.post("/v1/sources/waze/prices", json=body).status_code == 401
        assert (
            client.post(
                "/v1/sources/waze/prices", json=body, headers={"Authorization": "Bearer test"}
            ).status_code
            == 503
        )


def test_details_preserve_services_hours_and_payment_uncertainty():
    from gaswise.providers.waze.protocol import parse_stations

    hours = message(801, b"00:00") + message(802, b"00:00")
    hours += b"".join(number(803, day) for day in range(7))
    venue = message(104, b"Shell") + message(125, b"Shell") + message(117, b"US")
    venue += message(119, b"90029") + message(120, b"555-0100")
    venue += message(124, b"https://example.com") + message(110, b"CREDIT_CARDS")
    venue += message(110, b"FUTURE_SERVICE") + message(132, hours)
    product = message(1, b"gas_premium") + number_tag_float(4, 5.099)
    row = parse_stations(envelope(2742, message(1, message(1, venue + message(150, product)))))[0]
    assert row["details"]["open_now"] is True
    assert row["details"]["phone"] == "555-0100"
    assert row["details"]["accepts_credit_cards"] is True
    assert row["details"]["services"][-1]["id"] == "FUTURE_SERVICE"
    price = row["prices"][0]
    assert price["payment_type"] == "unknown" and price["octane"] is None
    assert price["octane_inference"]["estimated_octane"] == 91
    assert price["octane_inference"]["station_verified"] is False
    assert price["octane_inference"]["brand_octane_range"] == [91, 93]


def test_overnight_opening_hours_and_unknown_timezone():
    from datetime import datetime, timezone

    from gaswise.providers.waze.details import opening_status

    hours = [{"days": [5], "from": "22:00", "to": "02:00", "is_24_hours": False}]
    assert (
        opening_status(hours, "America/Los_Angeles", datetime(2026, 10, 10, 8, tzinfo=timezone.utc)) is True
    )
    assert (
        opening_status(hours, "America/Los_Angeles", datetime(2026, 10, 10, 10, tzinfo=timezone.utc)) is False
    )
    assert opening_status(hours, None) is None
    assert opening_status([], "America/Los_Angeles") is None


def test_grade_table_does_not_guess_outside_its_region_or_gasoline():
    from gaswise.domain.pricing.grades import infer_octane

    assert infer_octane("76", "US", "", "90029", "gas_premium")["estimated_octane"] == 91
    assert infer_octane("76", "US", "CO", "80202", "gas_premium") is None
    assert infer_octane("Shell", "CA", "", "", "gas_premium") is None
    assert infer_octane("Shell", "US", "CA", "90029", "gas_e85") is None
    assert infer_octane("76", "US", "CA", "90029", "plus")["estimated_octane"] == 89


def test_closed_business_overrides_weekly_open_hours():
    from gaswise.providers.waze.protocol import parse_stations

    hours = message(801, b"00:00") + message(802, b"00:00")
    hours += b"".join(number(803, day) for day in range(7))
    rating = number_tag_double(1, 4.2) + number(2, 604)
    google = message(2, rating) + number(3, 2)
    venue = message(104, b"76") + message(132, hours) + message(174, google)
    details = parse_stations(envelope(2742, message(1, message(1, venue))))[0]["details"]
    assert details["open_now"] is False
    assert details["google_attributes"]["rating"] == 4.2
    assert details["google_attributes"]["ratings_count"] == 604
    assert details["google_attributes"]["business_status"] == "temporarily_closed"
