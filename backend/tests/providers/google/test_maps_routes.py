import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.google.routes import MapsWebRouteProvider, WebRouteError
from tests.support.paths import FIXTURES as FIXTURE_ROOT


def observed(name="driving"):
    data = json.loads((FIXTURE_ROOT / f"maps_route_{name}.json").read_text())
    return data["response"], [Point.model_validate(p) for p in data["points"]]


def test_numeric_distance_and_traffic_in_observed_driving_route():
    data, points = observed()
    route = MapsWebRouteProvider.parse(data, points)
    assert (route.distance_meters, route.duration_seconds) == (3155, 529)
    assert route.duration_basis == "maps_traffic_estimate"
    assert route.source == "google_maps_web_directions"
    assert route.fetched_at.utcoffset().total_seconds() == 0


def test_three_point_roundtrip_is_not_doubled_outbound():
    data, points = observed("roundtrip")
    assert len(points) == 3 and points[0] == points[-1] and points[1] != points[0]
    route = MapsWebRouteProvider.parse(data, points)
    assert (route.distance_meters, route.duration_seconds) == (4505, 640)
    for wrong in ([points[0], points[-1]], [points[0], Point(lat=35, lng=-118), points[-1]]):
        with pytest.raises(ProviderError, match="waypoint_mismatch"):
            MapsWebRouteProvider.parse(data, wrong)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, "3155", None])
@pytest.mark.parametrize("field", ["distance", "traffic"])
def test_invalid_numbers_fail_without_base_duration_fallback(value, field):
    data, points = observed()
    if field == "distance":
        data[0][1][0][0][2][0] = value
    else:
        data[0][1][0][0][10][0][0] = value
    with pytest.raises(ProviderError, match="invalid_response"):
        MapsWebRouteProvider.parse(data, points)


def test_transit_only_and_malformed_responses_fail():
    data, points = observed()
    data[0][1] = [r for r in data[0][1] if r[0][0] != 0]
    with pytest.raises(ProviderError, match="no_driving_route"):
        MapsWebRouteProvider.parse(data, points)
    for bad in (None, {}, [], [[[]]]):
        with pytest.raises(ProviderError):
            MapsWebRouteProvider.parse(bad, points)


async def test_http_uses_two_fixed_google_requests():
    data, points = observed("roundtrip")
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.host == "www.google.com"
        if len(calls) == 1:
            assert request.url.path.startswith("/maps/dir/")
            for point in points:
                assert f"{point.lat},{point.lng}" in request.url.path
            return httpx.Response(
                200, text='<link rel="preload" as="fetch" href="/maps/preview/directions?pb=test">'
            )
        assert request.url.path == "/maps/preview/directions"
        return httpx.Response(200, text=")]}'\n" + json.dumps(data))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        route = await MapsWebRouteProvider(client).route(points[0], points[-1], points[1])
    assert len(calls) == route.upstream_http_requests == 2
    assert route.distance_meters == 4505


@pytest.mark.parametrize(
    "href",
    [
        "https://evil.example/maps/preview/directions",
        "//evil.example/maps/preview/directions",
        "/unrelated",
        "/maps/preview/directions#fragment",
    ],
)
async def test_untrusted_preload_never_receives_credentials(href):
    _, points = observed()
    calls = []

    class Session:
        def headers(self):
            return {"Cookie": "SID=synthetic-secret"}

    def respond(request):
        calls.append(request)
        assert request.url.host == "www.google.com"
        return httpx.Response(200, text=f'<link rel="preload" as="fetch" href="{href}">')

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(WebRouteError, match="schema_changed") as caught:
            await MapsWebRouteProvider(client, Session()).route(*points)
    assert len(calls) == caught.value.upstream_http_requests == 1
    assert "synthetic-secret" not in str(caught.value)


@pytest.mark.parametrize(
    "status,code",
    [
        (429, "rate_limited"),
        (403, "blocked_or_redirected"),
        (302, "blocked_or_redirected"),
        (500, "unavailable"),
    ],
)
@pytest.mark.parametrize("failure_attempt", [1, 2])
async def test_http_failure_counts_without_retry(status, code, failure_attempt):
    _, points = observed()
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == failure_attempt:
            return httpx.Response(status, headers={"Location": "https://evil.example/"})
        return httpx.Response(
            200, text='<link rel="preload" as="fetch" href="/maps/preview/directions?pb=test">'
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
        with pytest.raises(WebRouteError, match=code) as caught:
            await MapsWebRouteProvider(client).route(*points)
    assert len(calls) == caught.value.upstream_http_requests == failure_attempt


def test_prices_only_app_wires_website_router_without_paid_key(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("capabilities must not make network calls")

    monkeypatch.setattr(httpx.AsyncClient, "get", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    settings = Settings(
        mode="prices_only",
        gasbuddy_web_enabled=True,
        api_token="secret",
        maps_web_routes_enabled=True,
        google_api_key="",
    )
    with TestClient(create_app(settings)) as client:
        assert isinstance(client.app.state.services.smart.router, MapsWebRouteProvider)
        assert client.app.state.services.service is not None
        response = client.get("/v1/capabilities", headers={"Authorization": "Bearer secret"})
        assert response.status_code == 200
        assert response.json()["smart_routes_enabled"] is True
        assert response.json()["routing_source"] == "google_maps_web_directions"
        assert response.json()["fuel_consumption_model"] == "distance_fuel_balance_v1"
