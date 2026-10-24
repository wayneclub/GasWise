import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.sources import MapsWebSearch
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.google.maps_web import MapsWebProvider
from tests.support.paths import FIXTURES as FIXTURE_ROOT


def record(summary="$6.56/Regular"):
    row = [None] * 260
    row[2] = ["1516 Main St", "Los Angeles, CA 90015"]
    row[9] = [None, None, 34.0336356, -118.2622718]
    row[10], row[11], row[13], row[78], row[243] = "0xabc:0xdef", "Chevron", ["Gas station"], "fixture", "US"
    row[88] = [summary]
    return row


def query(**changes):
    return MapsWebSearch(origin={"lat": 34.0347, "lng": -118.2611}, **changes)


def test_summary_unknown_time_and_premium_not_substituted():
    row = record()
    regular = MapsWebProvider.parse([["gas stations", [[None] * 14 + [row]]]], query())
    assert str(regular.stations[0].price_per_gallon) == "6.56"
    assert regular.stations[0].price_updated_at is None
    assert regular.stations[0].payment_type == "unknown"
    premium = MapsWebProvider.parse([row], query(fuel_type="premium"))
    assert not premium.stations
    assert premium.inventory[0].available_fuel_types == ["regular"]


def test_full_fuel_structure_and_filtering():
    row = record()
    row[86] = [[["$6.96", 5, 1791544992, "gallon", 0, "USD", 6.96, "Premium"]], 3]
    result = MapsWebProvider.parse([row, row], query(fuel_type="premium"))
    assert len(result.stations) == 1
    assert result.stations[0].price_updated_at.timestamp() == 1791544992
    assert result.stations[0].octane is None
    row[9][2] = 35
    assert not MapsWebProvider.parse([row], query()).inventory
    row[9][2] = 34.0336356
    row[13] = ["Convenience store"]
    assert not MapsWebProvider.parse([row], query()).inventory


@pytest.mark.parametrize(
    "kind,price", [("regular", "6.56"), ("midgrade", "6.76"), ("premium", "6.96"), ("diesel", "8.46")]
)
def test_observed_browser_fuel_fields(kind, price):
    # Sanitized public station fields, preserving observed field 86 and its exact fuel rows.
    # This fixture verifies parsing; it does not claim anonymous HTTP returned the table.
    row = json.loads((FIXTURE_ROOT / "maps_web_fuel_observed.json").read_text())
    result = MapsWebProvider.parse([row], query(fuel_type=kind))
    assert str(result.stations[0].price_per_gallon) == price
    assert result.stations[0].price_updated_at is not None
    assert set(result.inventory[0].available_fuel_types) == {"regular", "midgrade", "premium", "diesel"}
    assert result.stations[0].octane is None


def test_invalid_full_fuel_does_not_hide_valid_sibling():
    row = record()
    row[86] = [
        [
            ["$1.00", 5, 1791544992, "gallon", 0, "USD", "NaN", "Premium"],
            ["$6.96", 5, 1791544992, "gallon", 0, "USD", 6.96, "Premium"],
            ["$1.00", 3, 1791544992, "gallon", 0, "USD", 1, "Premium"],
        ],
        3,
    ]
    result = MapsWebProvider.parse([row], query(fuel_type="premium"))
    assert len(result.stations) == 1
    assert str(result.stations[0].price_per_gallon) == "6.96"


async def test_one_anonymous_http_request_no_api_or_browser():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "www.google.com"
        assert request.url.params["tbm"] == "map"
        assert "key" not in request.url.params
        assert "cookie" not in request.headers
        assert "X-Goog-Api-Key" not in request.headers
        return httpx.Response(200, text=")]}'\n" + json.dumps([record()]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MapsWebProvider(client).prices(query())
    assert len(calls) == 1
    assert len(result.stations) == 1
    assert result.official_api_requests == 0


@pytest.mark.parametrize(
    "status,text", [(429, "blocked"), (302, ""), (200, "<html>challenge</html>"), (200, ")]}'\nnull")]
)
async def test_failure_no_retry_or_fallback(status, text):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=text, headers={"Location": "https://www.google.com/sorry/"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError):
            await MapsWebProvider(client).prices(query())
    assert len(calls) == 1


def test_endpoint_auth_no_store_and_no_google_key():
    settings = Settings(
        _env_file=None,
        mode="demo",
        api_token="fixture-token",
        google_api_key="",
        gasbuddy_web_enabled=False,
        waze_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/v1/sources/google-maps-web/prices", json=query().model_dump()).status_code == 401

        class Stub:
            async def prices(self, q):
                return MapsWebProvider.parse([record()], q)

        client.app.state.services.maps_web = Stub()
        response = client.post(
            "/v1/sources/google-maps-web/prices",
            json=query().model_dump(),
            headers={"Authorization": "Bearer fixture-token"},
        )
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()["stations"][0]["source"] == "google_maps_web"


def session_file(tmp_path, **changes):
    cookie = {"name": "SID", "value": "private-fixture", "domain": ".google.com", "path": "/", "expires": -1}
    cookie.update(changes)
    p = tmp_path / "session.json"
    p.write_text(json.dumps({"cookies": [cookie]}))
    p.chmod(0o600)
    return p


async def test_authenticated_search_full_fuels_single_request(tmp_path):
    row = json.loads((FIXTURE_ROOT / "maps_web_fuel_observed.json").read_text())
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "www.google.com"
        assert request.headers["Cookie"] == "SID=private-fixture"
        assert request.url.path == "/search"
        return httpx.Response(200, text=")]}'\n" + json.dumps([row]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MapsWebProvider(client, session_file(tmp_path)).prices(query(fuel_type="premium"))
    assert len(calls) == result.upstream_http_requests == 1
    assert result.detail_requests == 0
    assert result.authentication == "session"
    assert len(result.all_prices) == 4
    assert result.stations[0].fuel_type == "premium"


async def test_optional_details_bounded_and_identity_checked(tmp_path):
    rows = [record(), record()]
    rows[1][78] = "second"
    row = json.loads((FIXTURE_ROOT / "maps_web_fuel_observed.json").read_text())
    row[78] = "fixture"
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/search":
            return httpx.Response(200, text=")]}'\n" + json.dumps(rows))
        assert "key" not in request.url.params
        return httpx.Response(200, text=")]}'\n" + json.dumps([row]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MapsWebProvider(client, session_file(tmp_path)).prices(
            query(fuel_type="premium", detail_limit=1)
        )
    assert len(calls) == result.upstream_http_requests == 2
    assert result.detail_requests == 1
    assert len(result.stations) == 1
    assert len(result.all_prices) == 5  # four for the enriched station plus the other's Regular.


async def test_detail_rejection_stops_remaining_requests(tmp_path):
    rows = [record(), record()]
    rows[1][78] = "second"
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/search":
            return httpx.Response(200, text=")]}'\n" + json.dumps(rows))
        return httpx.Response(403, text="secret server body must not leak")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MapsWebProvider(client, session_file(tmp_path)).prices(
            query(fuel_type="premium", detail_limit=10)
        )
    assert len(calls) == 2
    assert "google_maps_web_session_rejected" in result.warnings
    assert not result.stations
    assert "private-fixture" not in result.model_dump_json()
    assert "secret server body" not in result.model_dump_json()


def detail_rows(count):
    # One priced Regular summary per station; full fuel tables arrive from details.
    rows = []
    for index in range(count):
        row = record()
        row[10] = f"0xabc{index}:0xdef{index}"
        row[78] = f"place-{index}"
        row[11] = f"Station {index}"
        rows.append(row)
    return rows


def detail_payload(rows, place):
    row = record()
    row[78] = place
    row[86] = [[["$6.96", 5, 1791544992, "gallon", 0, "USD", 6.96, "Premium"]], 3]
    return httpx.Response(200, text=")]}'\n" + json.dumps([row]))


async def test_detail_enrichment_is_bounded_but_concurrent(tmp_path):
    rows = detail_rows(5)
    places = {row[11]: row[78] for row in rows}
    calls = []

    def answer(request):
        calls.append(request.url.path)
        if request.url.path == "/search":
            return httpx.Response(200, text=")]}'\n" + json.dumps(rows))
        return detail_payload(rows, places[request.url.params["q"]])

    class Tracking(httpx.AsyncBaseTransport):
        active = peak = 0

        async def handle_async_request(self, request):
            if request.url.path == "/search":
                return answer(request)
            type(self).active += 1
            type(self).peak = max(type(self).peak, type(self).active)
            try:
                await asyncio.sleep(0.01)  # Hold the request open so overlap is observable.
                return answer(request)
            finally:
                type(self).active -= 1

    async with httpx.AsyncClient(transport=Tracking()) as client:
        result = await MapsWebProvider(client, session_file(tmp_path)).prices(
            query(fuel_type="premium", detail_limit=5)
        )
    # The first request is solo; the other four run as one bounded burst.
    assert Tracking.peak == 4
    assert result.detail_requests == 5
    assert result.upstream_http_requests == 6
    assert len(result.stations) == 5
    assert calls.count("/maps/preview/place") == 5


async def test_rejection_inside_a_detail_burst_stops_later_chunks(tmp_path):
    rows = detail_rows(9)
    places = {row[11]: row[78] for row in rows}
    detail_calls = []

    def answer(request):
        if request.url.path == "/search":
            return httpx.Response(200, text=")]}'\n" + json.dumps(rows))
        detail_calls.append(request)
        if request.url.params["q"] == "Station 2":
            return httpx.Response(403, text="secret server body must not leak")
        return detail_payload(rows, places[request.url.params["q"]])

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        result = await MapsWebProvider(client, session_file(tmp_path)).prices(
            query(fuel_type="premium", detail_limit=9)
        )
    # Solo first request, then one four-wide chunk that contains the rejection.
    # The final chunk of four is never sent.
    assert len(detail_calls) == 5
    assert result.detail_requests == 5
    assert "google_maps_web_session_rejected" in result.warnings
    assert "secret server body" not in result.model_dump_json()


@pytest.mark.parametrize("kind", ["expired", "public_file", "symlink", "invalid_header"])
async def test_invalid_session_no_network(tmp_path, kind):
    p = session_file(
        tmp_path,
        **(
            {"expires": 1}
            if kind == "expired"
            else {"value": "bad\r\nvalue"}
            if kind == "invalid_header"
            else {}
        ),
    )
    if kind == "public_file":
        p.chmod(0o644)
    if kind == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(p)
        p = link

    def handler(request):
        raise AssertionError("invalid credentials must fail before any request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError):
            await MapsWebProvider(client, p).prices(query(fuel_type="premium"))


async def test_detail_for_other_station_is_not_assigned(tmp_path):
    wrong = record()
    wrong[78] = "unrelated"
    wrong[86] = [[["$1.00", 5, 1791544992, "gallon", 0, "USD", 1, "Premium"]], 3]

    def handler(request):
        rows = [record()] if request.url.path == "/search" else [wrong]
        return httpx.Response(200, text=")]}'\n" + json.dumps(rows))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MapsWebProvider(client, session_file(tmp_path)).prices(
            query(fuel_type="premium", detail_limit=1)
        )
    assert not result.stations
    assert "google_maps_web_detail_identity_mismatch" in result.warnings
    assert all(s.fuel_type == "regular" for s in result.all_prices)


def opening_block(short, label):
    return [None, [None, 0, 4, None, [label, []], [label, []], None, None, [short, []]]]


@pytest.mark.parametrize(
    "short,label,open_now,status",
    [
        ("Open", "Open 24 hours", True, "operational"),
        ("Closes soon", "Closes soon · 10 PM", True, "operational"),
        ("Closed", "Closed · Opens 6 AM", False, "operational"),
        ("Opens soon", "Opens soon · 6 AM", False, "operational"),
        ("Permanently closed", "Permanently closed", False, "permanently_closed"),
        ("Temporarily closed", "Temporarily closed", False, "temporarily_closed"),
        ("Hours vary", "Hours vary", None, None),
    ],
)
def test_observed_opening_status_labels(short, label, open_now, status):
    # Structure observed on 2026-10-11: DTLA 24-hour stations and Irvine Costco at 2:36 AM.
    row = record()
    row[203] = opening_block(short, label)
    result = MapsWebProvider.parse([row], query())
    assert result.inventory[0].open_now is open_now
    assert result.inventory[0].business_status == status
    assert result.inventory[0].opening_status == label
    assert result.stations[0].open_now is open_now
    assert result.stations[0].details["opening_status"] == label


def test_missing_opening_block_is_unknown_not_open():
    result = MapsWebProvider.parse([record()], query())
    assert result.inventory[0].open_now is None and result.inventory[0].opening_status is None
    assert result.stations[0].open_now is None
    assert result.stations[0].details["location_source"] == "google_maps_web"


def test_public_rating_count_retained_and_invalid_rating_does_not_drop_station():
    row = record()
    row[4] = [None] * 7 + [4.2, 315]
    data = MapsWebProvider.parse([row], query())
    assert data.stations[0].rating == data.inventory[0].rating == 4.2
    assert data.stations[0].review_count == 315
    assert data.stations[0].rating_source == "Google Maps"
    row[4] = [None] * 7 + [float("nan"), "315"]
    data = MapsWebProvider.parse([row], query())
    assert len(data.stations) == 1
    assert data.stations[0].rating is None and data.stations[0].review_count is None


def test_permanently_closed_marker_without_hours_cannot_be_ranked_as_open():
    row = record()
    row[23], row[203] = 1, None
    result = MapsWebProvider.parse([row], query())
    assert result.inventory[0].open_now is False
    assert result.inventory[0].business_status == "permanently_closed"
    assert result.stations[0].business_status == "permanently_closed"


def test_mixed_payment_photo_prices_remain_unknown_per_fuel():
    row = record()
    row[86] = [[
        [f'${price}', kind, 1791544992, 'gallon', 0, 'USD', price, grade]
        for kind, grade, price in [(3, 'Regular', 5.86), (4, 'Midgrade', 6.06), (5, 'Premium', 6.04), (1, 'Diesel', 8.0)]
    ], 3]
    result = MapsWebProvider.parse([row], query(fuel_type='premium'))
    assert len(result.all_prices) == 4
    assert {r.payment_type for r in result.all_prices} == {'unknown'}
    assert str(result.stations[0].price_per_gallon) == '6.04'
