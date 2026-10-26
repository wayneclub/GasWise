import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.contracts.search import RankOptions
from gaswise.contracts.smart import SmartRerank, SmartSearch, SmartSnapshot
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.google.places import GoogleProvider
from gaswise.services.pricing.smart import SmartService
from tests.support.smart import (
    CountingProvider as CountingProvider,
)
from tests.support.smart import (
    MapsInventory as MapsInventory,
)
from tests.support.smart import (
    RawGasBuddy as RawGasBuddy,
)
from tests.support.smart import (
    WazeQuotes as WazeQuotes,
)
from tests.support.smart import (
    inventory as inventory,
)


async def test_rerank_changes_choice_with_zero_upstream_calls():
    provider = CountingProvider()
    service = SmartService(b"test", "demo", demo=provider)
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    assert first.ranking.results[0].station.name == "Arco"
    counts = provider.searches, provider.routes
    changed = await service.rerank(
        SmartRerank(
            snapshot=first.snapshot,
            signature=first.signature,
            options=RankOptions(strategy="best_value", time_value_per_hour="60"),
        )
    )
    assert changed.ranking.results[0].station.name == "Chevron"
    assert (provider.searches, provider.routes) == counts
    assert not any(changed.upstream_calls.values())
    assert changed.snapshot.collected_at == first.snapshot.collected_at
    assert changed.ranking.results[0].station.price_updated_at == first.snapshot.stations[0].price_updated_at


async def test_tampered_and_expired_snapshots_fail_without_network():
    service = SmartService(b"test", "demo", demo=CountingProvider())
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    bad = first.snapshot.model_copy(deep=True)
    from decimal import Decimal

    bad.stations[0].price_per_gallon = Decimal("0.01")
    with pytest.raises(ProviderError, match="invalid_snapshot_signature"):
        await service.rerank(SmartRerank(snapshot=bad, signature=first.signature, options=RankOptions()))
    old = first.snapshot.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    with pytest.raises(ProviderError, match="snapshot_expired"):
        await service.rerank(SmartRerank(snapshot=old, signature=service.sign(old), options=RankOptions()))


async def test_concurrent_clicks_coalesce_but_explicit_new_search_refreshes():
    provider = CountingProvider()
    gate = asyncio.Event()
    entered = asyncio.Event()
    original = provider.stations

    async def slow(query):
        entered.set()
        await gate.wait()
        return await original(query)

    provider.stations = slow
    service = SmartService(b"test", "demo", demo=provider)
    query = SmartSearch(origin=Point(lat=34, lng=-118))
    one = asyncio.create_task(service.search(query))
    await entered.wait()
    two = asyncio.create_task(service.search(query))
    await asyncio.sleep(0)
    gate.set()
    a, b = await asyncio.gather(one, two)
    assert a.signature == b.signature
    assert provider.searches == 1
    await service.search(query)
    assert provider.searches == 2
    assert not service.inflight


async def test_routes_disabled_fails_before_discovery():
    service = SmartService(b"test", "prices_only")
    with pytest.raises(ProviderError, match="smart_routing_not_configured"):
        await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))


async def test_no_routes_is_explicit_not_estimated_cost():
    service = SmartService(b"test", "demo", demo=CountingProvider())
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert first.ranking is None
    with pytest.raises(ProviderError, match="snapshot_has_no_routes"):
        await service.rerank(
            SmartRerank(snapshot=first.snapshot, signature=first.signature, options=RankOptions())
        )


async def test_one_nearby_matches_gasbuddy_without_text_or_routes():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        assert request.url.path == "/v1/places:searchNearby"
        return httpx.Response(200, json=inventory())

    gb = RawGasBuddy()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = SmartService(b"test", "prices_only", gasbuddy=gb, google=GoogleProvider(client, "fixture"))
        result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert gb.calls == 1 and len(calls) == 1
    assert result.upstream_calls == {
        "gasbuddy_search": 1,
        "gasbuddy_pages": 1,
        "google_nearby": 1,
        "google_text_search": 0,
        "routes": 0,
    }
    assert result.snapshot.stations[0].source == "gasbuddy_web"
    assert result.snapshot.stations[0].canonical_id == "google_places:gp1"
    assert result.snapshot.stations[0].details["location_source"] == "google_places"
    assert not result.snapshot.unlocated_gasbuddy
    assert result.ranking is None


async def test_missing_location_preserves_raw_quotes_without_guessing():
    service = SmartService(b"test", "prices_only", gasbuddy=RawGasBuddy())
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert not result.snapshot.stations
    assert len(result.snapshot.unlocated_gasbuddy) == 1
    assert result.upstream_calls["google_nearby"] == 0


async def test_candidate_routes_are_bounded_and_exclude_stale_quotes():
    provider = CountingProvider(stale=True)
    service = SmartService(b"test", "demo", demo=provider)
    result = await service.search(
        SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, route_limit=2)
    )
    assert provider.routes == 0
    assert not result.ranking.results


def test_smart_http_auth_and_input_contract():
    provider = CountingProvider()
    with TestClient(create_app(Settings(api_token="secret"), provider)) as client:
        body = {"origin": {"lat": 34, "lng": -118}, "calculate_routes": True}
        assert client.post("/v1/smart/search", json=body).status_code == 401
        headers = {"Authorization": "Bearer secret"}
        first = client.post("/v1/smart/search", json=body, headers=headers)
        assert first.status_code == 200
        assert first.headers["cache-control"] == "no-store"
        data = first.json()
        rerank = {"snapshot": data["snapshot"], "signature": data["signature"], "options": {"gallons": "5"}}
        response = client.post("/v1/smart/rerank", json=rerank, headers=headers)
        assert response.status_code == 200
        assert provider.searches == 1
        rerank["options"]["origin"] = {"lat": 35, "lng": -118}
        assert client.post("/v1/smart/rerank", json=rerank, headers=headers).status_code == 422


def test_progressive_search_job_returns_before_slow_source_and_polls_completed_result():
    class SlowProvider(CountingProvider):
        async def stations(self, query, *, all_fuels=False):
            await asyncio.sleep(.2)
            return await super().stations(query)

    with TestClient(create_app(Settings(api_token="secret"), SlowProvider())) as client:
        headers = {"Authorization": "Bearer secret"}
        started = client.post(
            "/v1/smart/search-jobs/start",
            headers=headers,
            json={"origin": {"lat": 34, "lng": -118}, "calculate_routes": True},
        )
        assert started.status_code == 200
        job = started.json()
        assert job["status"] == "pending" and job["revision"] == 0 and job["result"] is None

        response = None
        for _ in range(20):
            response = client.post(
                "/v1/smart/search-jobs/poll",
                headers=headers,
                json={"job_id": job["job_id"], "after_revision": 0},
            )
            if response.json()["status"] == "complete":
                break
            __import__("time").sleep(.02)
        assert response is not None and response.status_code == 200
        completed = response.json()
        assert completed["status"] == "complete" and completed["revision"] == 1
        assert completed["result"]["ranking"]["results"]


async def test_progressive_search_publishes_each_live_source_as_a_revision():
    class SlowWaze(WazeQuotes):
        async def stations(self, query, *, all_fuels=False):
            await asyncio.sleep(.1)
            return await super().stations(query)

    service = SmartService(
        b"test", "prices_only", maps_web=MapsInventory(), waze=SlowWaze(), router=CountingProvider()
    )
    started = await service.start_progressive_search(
        SmartSearch(
            origin=Point(lat=34, lng=-118),
            fuel_type="premium",
            calculate_routes=True,
            allow_unknown_payment=True,
        )
    )
    assert started.revision == 0
    partial = None
    for _ in range(20):
        await asyncio.sleep(.01)
        state = await service.poll_progressive_search(started.job_id)
        if state.revision == 1:
            partial = state
            break
    assert partial is not None
    assert partial.status == "partial"
    assert partial.completed_sources == ["maps"]
    assert partial.result.ranking.results

    await asyncio.sleep(.12)
    complete = await service.poll_progressive_search(started.job_id)
    assert complete.status == "complete"
    assert complete.revision == 2
    assert set(complete.completed_sources) == {"maps", "waze"}
    assert {row.source for row in complete.result.snapshot.stations} >= {"google_maps_web", "waze"}
    await service.close()


async def test_progressive_empty_town_is_complete_not_source_failure():
    class EmptyMaps(MapsInventory):
        async def prices(self, query):
            data = await super().prices(query)
            return data.model_copy(update={"inventory": [], "stations": []})

    service = SmartService(b"test", "prices_only", maps_web=EmptyMaps(), router=CountingProvider())
    job = await service.start_progressive_search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    await asyncio.gather(*service.progressive_tasks)
    state = await service.poll_progressive_search(job.job_id)
    assert state.status == "complete"
    assert state.result.snapshot.stations == []
    assert state.result.snapshot.inventory == []
    assert state.result.snapshot.source_statuses[0].status == "ok"
    assert state.result.ranking.results == []
    await service.close()


async def test_progressive_all_failed_sources_preserve_failure_evidence():
    class BrokenWaze(WazeQuotes):
        async def stations(self, query, *, all_fuels=False):
            raise ProviderError("waze_timeout")

    service = SmartService(b"test", "prices_only", waze=BrokenWaze(), router=CountingProvider())
    job = await service.start_progressive_search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    await asyncio.gather(*service.progressive_tasks)
    state = await service.poll_progressive_search(job.job_id)
    assert state.status == "complete"
    assert state.result.snapshot.stations == []
    assert state.result.snapshot.source_statuses[0].status == "unavailable"
    assert state.result.snapshot.source_statuses[0].detail == "waze_timeout"
    await service.close()


async def test_separate_routing_stage_does_not_refetch_prices():
    from gaswise.contracts.smart import SmartRouteRequest

    provider = CountingProvider()
    service = SmartService(b"test", "demo", demo=provider)
    prices = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), mpg="25"))
    routed = await service.add_routes(
        SmartRouteRequest(
            snapshot=prices.snapshot,
            signature=prices.signature,
            route_limit=2,
        )
    )
    assert provider.searches == 1 and provider.routes == 2
    assert len(routed.snapshot.routes) == 2
    again = await service.add_routes(SmartRouteRequest(snapshot=routed.snapshot, signature=routed.signature))
    assert provider.routes == 2
    assert not any(again.upstream_calls.values())
    re = await service.rerank(
        SmartRerank(snapshot=routed.snapshot, signature=routed.signature, options=RankOptions(gallons="5"))
    )
    assert re.ranking.results
    # Partial options preserve MPG from original search rather than resetting to 20.
    row = re.ranking.results[0]
    assert row.detour_fuel_cost == (row.detour_miles / 25 * row.station.price_per_gallon).quantize(
        __import__("decimal").Decimal("0.01")
    )


def test_live_routes_guard_prevents_all_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    settings = Settings(
        mode="prices_only", gasbuddy_web_enabled=True, google_api_key="fixture", api_token="secret"
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/smart/search",
            headers={"Authorization": "Bearer secret"},
            json={"origin": {"lat": 34, "lng": -118}, "calculate_routes": True},
        )
    assert response.status_code == 503


async def test_google_quota_error_keeps_raw_gasbuddy_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = SmartService(
            b"test", "prices_only", gasbuddy=RawGasBuddy(), google=GoogleProvider(client, "fixture")
        )
        result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert len(calls) == 1
    assert len(result.snapshot.unlocated_gasbuddy) == 1
    assert result.snapshot.source_statuses[-1].status == "unavailable"
    assert result.ranking is None


async def test_sequential_reranks_preserve_new_options_and_original_expiry():
    service = SmartService(b"test", "demo", demo=CountingProvider())
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    changed = await service.rerank(
        SmartRerank(snapshot=first.snapshot, signature=first.signature, options=RankOptions(gallons="15"))
    )
    next_change = await service.rerank(
        SmartRerank(snapshot=changed.snapshot, signature=changed.signature, options=RankOptions(mpg="25"))
    )
    assert next_change.snapshot.query.gallons == 15
    assert next_change.snapshot.query.mpg == 25
    assert next_change.snapshot.expires_at == first.snapshot.expires_at
    assert next_change.snapshot.collected_at == first.snapshot.collected_at


async def test_three_sources_share_inventory_routes_and_keep_payment_evidence():
    gb, maps, waze, router = RawGasBuddy(), MapsInventory(), WazeQuotes(), CountingProvider()

    class PaidPlacesForbidden:
        async def nearby_places(self, query):
            raise AssertionError("no paid fallback when Maps website is selected")

    service = SmartService(
        b"test", "google", gasbuddy=gb, maps_web=maps, waze=waze, google=PaidPlacesForbidden(), router=router
    )
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    assert (gb.calls, maps.calls, waze.calls, router.routes) == (1, 1, 1, 1)
    assert len(first.snapshot.stations) == 3
    assert {s.canonical_id for s in first.snapshot.stations} == {"google_places:gp1"}
    assert all(s.details.get("location_source") == "google_maps_web" for s in first.snapshot.stations)
    assert len(first.ranking.results) == 1
    row = first.ranking.results[0]
    assert row.station.source == "gasbuddy_web"
    assert {e.source for e in row.price_comparison.evidence} == {"gasbuddy_web", "waze", "google_maps_web"}
    assert row.price_comparison.eligible_source_count == 1
    assert all(not e.eligible for e in row.price_comparison.evidence if e.payment_type == "unknown")
    assert first.upstream_calls["google_nearby"] == 0
    assert first.upstream_calls["routes"] == 1
    assert {"discovery_gasbuddy", "discovery_maps", "discovery_waze", "routes", "aaa_averages"} <= first.timings_ms.keys()
    changed = await service.rerank(
        SmartRerank(
            snapshot=first.snapshot,
            signature=first.signature,
            options=RankOptions(gallons="15"),
        )
    )
    assert (gb.calls, maps.calls, waze.calls, router.routes) == (1, 1, 1, 1)
    assert not any(changed.upstream_calls.values())


async def test_gasbuddy_zip_plus_four_matches_maps_inventory():
    class ZipPlusFour(RawGasBuddy):
        async def prices(self, query):
            data = await super().prices(query)
            data.prices[0].address += "-1230"
            data.prices[0].postal_code += "-1230"
            return data

    service = SmartService(b"test", "prices_only", gasbuddy=ZipPlusFour(), maps_web=MapsInventory())
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert not result.snapshot.unlocated_gasbuddy
    assert (
        next(s for s in result.snapshot.stations if s.source == "gasbuddy_web").canonical_id
        == "google_places:gp1"
    )


def test_routes_switch_blocks_legacy_endpoints_and_capabilities(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("routing switch must guard every recommendation endpoint")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    settings = Settings(
        mode="google", google_api_key="fixture", api_token="secret", google_routes_enabled=False
    )
    headers = {"Authorization": "Bearer secret"}
    with TestClient(create_app(settings)) as api:
        for path in ("/v1/recommendations", "/v1/recommendations/stream", "/v1/smart/search"):
            response = api.post(
                path,
                headers=headers,
                json={
                    "origin": {"lat": 34, "lng": -118},
                    **({"calculate_routes": True} if path.endswith("search") else {}),
                },
            )
            assert response.status_code == 503
        capabilities = api.get("/v1/capabilities", headers=headers).json()
        assert capabilities["recommendations_enabled"] is False
        assert capabilities["smart_routes_enabled"] is False


async def test_maps_failure_preserves_raw_gasbuddy_and_waze_without_paid_fallback():
    class BrokenMaps:
        async def prices(self, query):
            raise ProviderError("google_maps_web_session_rejected")

    service = SmartService(
        b"test", "prices_only", gasbuddy=RawGasBuddy(), maps_web=BrokenMaps(), waze=WazeQuotes()
    )
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert len(result.snapshot.unlocated_gasbuddy) == 1
    assert result.snapshot.stations[0].source == "waze"
    assert result.upstream_calls["google_nearby"] == 0
    assert (
        next(s for s in result.snapshot.source_statuses if s.source == "google_maps_web").status
        == "unavailable"
    )


class NoLane:
    def __init__(self, error="pricing_egress_unavailable"):
        self.error = error

    async def prices(self, query):
        raise ProviderError(self.error)

    async def stations(self, query, *, all_fuels=False):
        raise ProviderError(self.error)


async def test_all_sources_without_a_verified_lane_defer_with_the_lane_code():
    service = SmartService(
        b"test", "prices_only", gasbuddy=NoLane(), maps_web=NoLane(), waze=NoLane()
    )
    with pytest.raises(ProviderError) as error:
        await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    # Every failure carries the actionable lane code, not a generic outage.
    assert str(error.value) == "pricing_egress_unavailable"


async def test_mixed_source_failures_keep_the_existing_unavailable_code():
    service = SmartService(
        b"test",
        "prices_only",
        gasbuddy=NoLane("gasbuddy_http_unavailable"),
        maps_web=NoLane("google_maps_web_unavailable"),
        waze=NoLane("waze_upstream_unavailable"),
    )
    with pytest.raises(ProviderError, match="^smart_price_sources_unavailable$"):
        await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))


async def test_unknown_only_sources_do_not_rank_unless_explicitly_allowed():
    router = CountingProvider()
    service = SmartService(b"test", "google", maps_web=MapsInventory(), waze=WazeQuotes(), router=router)
    strict = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    assert not strict.ranking.results and router.routes == 0
    allowed = await service.search(
        SmartSearch(
            origin=Point(lat=34, lng=-118),
            calculate_routes=True,
            allow_unknown_payment=True,
        )
    )
    assert len(allowed.ranking.results) == 1 and router.routes == 1
    assert allowed.ranking.results[0].price_comparison.quality != "corroborated"
    assert any("explicitly allowed" in w for w in allowed.ranking.warnings)


async def test_google_failure_does_not_prevent_waze_collection():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(429))) as client:
        service = SmartService(
            b"test", "prices_only", google=GoogleProvider(client, "fixture"), waze=WazeQuotes()
        )
        result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert result.snapshot.stations[0].source == "waze"


async def test_web_route_snapshot_counts_http_and_rerank_has_zero_calls():
    from gaswise.contracts.common import Route

    class WebsiteRouter:
        http_counter_name = "maps_web_route_http_requests"
        requests = 0

        async def route(self, origin, destination, via=None):
            self.requests += 2
            # Realistic asymmetric route increments, not doubled outbound travel.
            return Route(
                distance_meters=5000 if via else 4000,
                duration_seconds=720 if via else 600,
                source="google_maps_web_directions",
                duration_basis="maps_traffic_estimate",
                upstream_http_requests=2,
            )

    router = WebsiteRouter()
    service = SmartService(
        b"test", "prices_only", gasbuddy=RawGasBuddy(), maps_web=MapsInventory(), router=router
    )
    first = await service.search(
        SmartSearch(
            origin=Point(lat=34, lng=-118),
            destination=Point(lat=34.1, lng=-118),
            trip_mode="on_route",
            calculate_routes=True,
        )
    )
    assert first.upstream_calls["routes"] == 2  # baseline + one station
    assert first.upstream_calls["maps_web_route_http_requests"] == 4
    assert first.ranking.mode == "prices_only"
    assert first.ranking.results[0].extra_travel_minutes == 2
    row = first.ranking.results[0]
    assert row.mpg_used == 20
    assert row.fuel_consumption_basis == "user_mpg_estimate"
    assert abs(float(row.detour_fuel_gallons) - (1000 / 1609.344 / 20)) < 1e-10
    changed = await service.rerank(
        SmartRerank(
            snapshot=first.snapshot,
            signature=first.signature,
            options=RankOptions(mpg="25"),
        )
    )
    assert router.requests == 4
    assert not any(changed.upstream_calls.values())
    assert changed.ranking.results[0].mpg_used == 25


async def test_web_route_failure_counts_attempts_without_straight_line_cost():
    from gaswise.providers.google.routes import WebRouteError

    class WebsiteRouter:
        http_counter_name = "maps_web_route_http_requests"

        async def route(self, origin, destination, via=None):
            raise WebRouteError("google_maps_web_route_schema_changed", upstream_http_requests=1)

    service = SmartService(
        b"test", "prices_only", gasbuddy=RawGasBuddy(), maps_web=MapsInventory(), router=WebsiteRouter()
    )
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    assert not result.ranking.results
    assert result.upstream_calls["routes"] == 1
    assert result.upstream_calls["maps_web_route_http_requests"] == 1
    assert any("Route unavailable" in w for w in result.ranking.warnings)


async def test_closed_inventory_station_excludes_matched_quotes_before_routing():
    class ClosedMaps(MapsInventory):
        async def prices(self, query):
            data = await super().prices(query)
            data.inventory[0].open_now = False
            data.inventory[0].opening_status = "Closed · Opens 6 AM"
            data.stations = []  # Search cards often lack the requested grade.
            return data

    router = CountingProvider()
    service = SmartService(b"test", "google", gasbuddy=RawGasBuddy(), maps_web=ClosedMaps(), router=router)
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    gasbuddy = next(s for s in result.snapshot.stations if s.source == "gasbuddy_web")
    assert gasbuddy.open_now is False
    assert gasbuddy.details["location_source"] == "google_maps_web"
    assert result.ranking.results == [] and router.routes == 0
    reopened = await service.rerank(
        SmartRerank(
            snapshot=result.snapshot,
            signature=result.signature,
            options=RankOptions(opening_policy="ignore"),
        )
    )
    assert reopened.ranking.results == []  # Closed stations were never routed.


async def test_signature_survives_browser_json_round_trip():
    import json

    service = SmartService(b"test", "demo", demo=CountingProvider())
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))
    snapshot = first.snapshot.model_dump(mode="json")
    # Waze details carry untyped floats such as rating 3.0; JavaScript re-serializes them as 3,
    # and orders integer-like object keys first.
    snapshot["stations"][0]["details"] = {"rating": 3.0, "b": 1, "10": "x", "2": "y"}
    signed = SmartSnapshot.model_validate(snapshot)
    signature = service.sign(signed)
    # Normalize numeric fields explicitly: replacing text in serialized JSON can
    # corrupt timestamps containing seconds such as "43.012345".
    browser = json.loads(json.dumps(snapshot))
    browser["stations"][0]["details"] = {"2": "y", "10": "x", "rating": 3, "b": 1}
    browser["query"]["radius_meters"] = int(browser["query"]["radius_meters"])
    result = await service.rerank(
        SmartRerank(
            snapshot=SmartSnapshot.model_validate(browser), signature=signature, options=RankOptions()
        )
    )
    assert result.ranking is not None
    tampered = dict(
        browser, stations=[dict(browser["stations"][0], price_per_gallon="0.01")] + browser["stations"][1:]
    )
    with pytest.raises(ProviderError, match="invalid_snapshot_signature"):
        await service.rerank(
            SmartRerank(
                snapshot=SmartSnapshot.model_validate(tampered), signature=signature, options=RankOptions()
            )
        )


async def test_expand_routes_uses_original_prices_and_does_not_repeat_cached_route():
    from gaswise.contracts.smart import SmartRouteRequest
    provider = CountingProvider()
    service = SmartService(b"test", "demo", demo=provider)
    initial = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, route_limit=0, estimate_unrouted_routes=True))
    assert initial.coverage.routed == 0
    assert initial.ranking is not None
    assert any(r.route.source == "straight_line_estimate" for r in initial.ranking.results)
    assert provider.routes == 0
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, route_limit=1))
    assert first.coverage.eligible > first.coverage.routed
    price_calls, initial_routes = provider.searches, provider.routes
    expanded = await service.add_routes(SmartRouteRequest(snapshot=first.snapshot, signature=first.signature, route_limit=10))
    assert expanded.coverage.routed > first.coverage.routed
    assert provider.searches == price_calls
    assert provider.routes - initial_routes == len(expanded.snapshot.routes) - len(first.snapshot.routes)
    counts = provider.searches, provider.routes
    await service.add_routes(SmartRouteRequest(snapshot=expanded.snapshot, signature=expanded.signature, route_limit=10))
    assert counts == (provider.searches, provider.routes)


async def test_coverage_explains_excluded_quotes_using_domain_rules():
    provider = CountingProvider()
    service = SmartService(b"test", "demo", demo=provider)
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, payment_type="cash"))
    assert first.coverage.displayed == 0
    assert first.coverage.exclusions["payment_type_mismatch"] > 0
    assert first.coverage.priced == first.coverage.discovered


async def test_coverage_reason_matches_the_quote_shown_to_the_browser():
    from gaswise.contracts.smart import SmartResult
    from tests.support.comparison import NOW, quote
    expired = quote("gasbuddy_web", "gb1", "6.00", age=1500, canonical_id="google_places:a")
    unknown = quote("waze", "venue1", "5.00", canonical_id="google_places:a").model_copy(update={"payment_type": "unknown"})
    query = SmartSearch(origin=expired.location, fuel_type="premium", payment_type="cash_or_credit")
    snapshot = SmartSnapshot(query=query, stations=[unknown, expired], source_statuses=[], collected_at=NOW, expires_at=NOW + timedelta(minutes=10))
    result = SmartResult(snapshot=snapshot, signature="x" * 64, upstream_calls={})
    assert result.coverage.quote_indices["google_places:a"] == 1
    assert result.coverage.station_statuses["google_places:a"] == "stale_price"


async def test_expanded_discovery_compares_every_known_open_eligible_station(monkeypatch):
    from gaswise.contracts.common import Route, Station
    from gaswise.contracts.sources import MapsWebPrices, MapsWebStation

    async def no_pause(_):
        pass

    monkeypatch.setattr('gaswise.services.pricing.smart.asyncio.sleep', no_pause)

    class TiledMaps:
        calls = 0

        async def prices(self, query):
            self.calls += 1
            now = datetime.now(UTC)
            inventory, stations = [], []
            # Overlapping viewports contain duplicates and progressively new stations.
            for i in range((self.calls - 1) * 3, self.calls * 3 + 2):
                point = Point(lat=34 + i * 0.001, lng=-118)
                opened = False if i == 0 else None if i == 1 else True
                inventory.append(MapsWebStation(place_id=str(i), name=f'Station {i}', location=point, distance_meters=i * 111, available_fuel_types=['premium'], open_now=opened))
                stations.append(Station(id=str(i), canonical_id=f'google_places:{i}', name=f'Station {i}', location=point, fuel_type='premium', octane=91, payment_type='credit', price_per_gallon='6', price_updated_at=now, fetched_at=now, source='google_maps_web', open_now=opened))
            # Full pages that reach only 150m: each request proves a small disk, so discovery continues.
            return MapsWebPrices(inventory=inventory, stations=stations, all_prices=[], warnings=[], candidate_count=20, candidate_reach_meters=150)

    class Router:
        calls = 0

        async def route(self, origin, destination, via=None):
            self.calls += 1
            return Route(distance_meters=1000, duration_seconds=120, source='fixture')

    maps, router = TiledMaps(), Router()
    result = await SmartService(b'test', 'google', maps_web=maps, router=router).search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, discovery_tiles=5, route_limit=100, max_results=100, opening_policy='require_open'))
    assert maps.calls == 5 and result.upstream_calls['google_maps_web_search'] == 5
    assert len(result.snapshot.inventory) == 17
    assert result.coverage.eligible == result.coverage.routed == len(result.ranking.results) == router.calls == 15
    assert all(row.station.open_now is True for row in result.ranking.results)
    assert result.coverage.exclusions['station_closed'] == 1
    assert result.coverage.exclusions['opening_status_unknown'] == 1
    limited = await SmartService(b'test', 'google', maps_web=maps, router=router).rerank(SmartRerank(snapshot=result.snapshot, signature=result.signature, options=RankOptions(opening_policy='require_open', max_results=2)))
    assert limited.coverage.routed == 15 and limited.coverage.displayed == 2
    assert not any(limited.upstream_calls.values())


async def test_discovery_stops_on_rate_limit_and_preserves_completed_viewport(monkeypatch):
    async def no_pause(_):
        pass

    monkeypatch.setattr('gaswise.services.pricing.smart.asyncio.sleep', no_pause)

    class LimitedMaps(MapsInventory):
        async def prices(self, query):
            if self.calls:
                self.calls += 1
                raise ProviderError('google_maps_web_rate_limited')
            page = await super().prices(query)
            return page.model_copy(update={'candidate_count': 20, 'candidate_reach_meters': 100})

    maps = LimitedMaps()
    result = await SmartService(b'test', 'google', maps_web=maps).search(SmartSearch(origin=Point(lat=34, lng=-118), discovery_tiles=5))
    assert maps.calls == result.upstream_calls['google_maps_web_search'] == 2
    assert len(result.snapshot.inventory) == 1
    assert any('Discovery stopped for viewport' in warning for warning in result.snapshot.warnings)


async def test_unknown_payment_credit_estimate_preserves_raw_quote_and_does_not_compound():
    from decimal import Decimal

    class UnknownProvider(CountingProvider):
        async def stations(self, query, *, all_fuels=False):
            rows = await super().stations(query)
            rows[0].payment_type = 'unknown'
            rows[0].open_now = True
            return rows

    provider = UnknownProvider()
    service = SmartService(b'test', 'demo', demo=provider)
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True, max_results=100, allow_unknown_payment=True, unknown_payment_credit_markup='0.20'))
    raw = next(s for s in first.snapshot.stations if s.id == 'Chevron')
    row = next(r for r in first.ranking.results if r.station.id == 'Chevron')
    assert raw.price_per_gallon == row.station.price_per_gallon == Decimal('6.39')
    assert raw.comparison_price_per_gallon is None
    assert row.station.comparison_price_per_gallon == Decimal('6.59')
    assert row.station.payment_type == 'unknown'
    assert row.purchase_cost == Decimal('65.90')
    assert row.price_comparison.evidence[0].price_per_gallon == Decimal('6.39')
    counts = provider.searches, provider.routes
    for _ in range(2):
        first = await service.rerank(SmartRerank(snapshot=first.snapshot, signature=first.signature, options=RankOptions(allow_unknown_payment=True, unknown_payment_credit_markup='0.20', max_results=100)))
        row = next(r for r in first.ranking.results if r.station.id == 'Chevron')
        assert row.purchase_cost == Decimal('65.90')
        assert not any(first.upstream_calls.values())
    assert (provider.searches, provider.routes) == counts
    cash = await service.rerank(SmartRerank(snapshot=first.snapshot, signature=first.signature, options=RankOptions(payment_type='cash', allow_unknown_payment=True, unknown_payment_credit_markup='0.20')))
    assert cash.ranking.results[0].station.comparison_price_per_gallon is None
    assert cash.ranking.results[0].purchase_cost == Decimal('63.90')


class PlacedGasBuddy(RawGasBuddy):
    """GasBuddy listing that carries the station's own coordinates."""

    queries = []

    async def prices(self, query):
        self.queries.append(query)
        data = await super().prices(query)
        data.prices[0].location = Point(lat=34.0101, lng=-118)
        data.prices[0].address = data.prices[0].address.replace("1516", "1600")
        return data


async def test_gasbuddy_searches_by_coordinates_and_keeps_unmatched_located_quotes():
    gb = PlacedGasBuddy()
    service = SmartService(b"test", "prices_only", gasbuddy=gb, maps_web=MapsInventory())
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), postal_code="90015", radius_meters=1609))
    query = gb.queries[-1]
    # ZIP searches stop at the ZIP line; the coordinate search covers the radius plus its soft buffer.
    assert query.postal_code is None and query.origin is not None
    assert query.radius_meters >= 1609 + 800
    placed = next(s for s in result.snapshot.stations if s.source == "gasbuddy_web")
    assert placed.canonical_id == "gasbuddy:gb1"
    assert placed.location == Point(lat=34.0101, lng=-118)
    assert placed.attribution == ["GasBuddy"]
    assert not result.snapshot.unlocated_gasbuddy


async def test_waze_quote_joins_gasbuddy_placed_site_instead_of_a_second_card():
    class SameSiteWaze(WazeQuotes):
        async def stations(self, query, *, all_fuels=False):
            rows = await super().stations(query)
            return [rows[0].model_copy(update={"location": Point(lat=34.01011, lng=-118), "address": "1600 S Main St Los Angeles CA 90015"})]

    service = SmartService(b"test", "prices_only", gasbuddy=PlacedGasBuddy(), waze=SameSiteWaze())
    result = await service.search(SmartSearch(origin=Point(lat=34, lng=-118)))
    assert {s.canonical_id for s in result.snapshot.stations} == {"gasbuddy:gb1"}


def test_soft_radius_keeps_stations_just_past_the_boundary():
    from gaswise.domain.pricing.comparison import ineligible, search_limit_meters

    query = SmartSearch(origin=Point(lat=34, lng=-118), radius_meters=8047, fuel_type="premium", payment_type="cash_or_credit")
    assert search_limit_meters(query) == pytest.approx(8047 * 1.2)
    now = datetime.now(UTC)

    def at(meters):
        from gaswise.contracts.common import Station

        return Station(id="s", name="S", location=Point(lat=34 + meters / 111195, lng=-118), fuel_type="premium",
                       price_per_gallon="5", payment_type="credit", price_updated_at=now, fetched_at=now, source="fixture")

    assert ineligible(at(9000), query, now) is None
    assert ineligible(at(9800), query, now) == "outside_search_radius"


async def test_twenty_precise_routes_keep_all_fifty_candidates_and_expand_without_prices():
    from gaswise.contracts.common import Route
    from gaswise.contracts.smart import SmartRouteRequest
    from gaswise.domain.pricing.comparison import distance_meters

    class ManyStations(CountingProvider):
        async def stations(self, query, *, all_fuels=False):
            templates = await super().stations(query)
            return [templates[0].model_copy(update={
                "id": f"station-{i}", "name": f"Station {i}",
                "location": Point(lat=34 + i * .0005, lng=-118),
            }) for i in range(50)]

        async def route(self, origin, destination, via=None):
            self.routes += 1
            distance = 2 * distance_meters(origin, via)
            return Route(distance_meters=distance * 1.5, duration_seconds=distance / 10, source="fixture")

    provider = ManyStations()
    service = SmartService(b"test", "demo", demo=provider)
    result = await service.search(SmartSearch(
        origin=Point(lat=34, lng=-118), calculate_routes=True,
        estimate_unrouted_routes=True, route_limit=100, max_results=100,
    ))
    assert provider.routes == 20
    assert len(result.ranking.results) == 50
    assert result.coverage.routed == 20
    assert list(result.coverage.station_statuses.values()).count("estimated_route") == 30
    assert sum(row.route.source == "straight_line_estimate" for row in result.ranking.results) == 30
    assert result.ranking.decision.status == "uncertain"
    searches = provider.searches
    reranked = await service.rerank(SmartRerank(
        snapshot=result.snapshot, signature=result.signature, options=RankOptions(gallons=20),
    ))
    assert provider.routes == 20 and provider.searches == searches
    assert len(reranked.ranking.results) == 50
    expanded = await service.add_routes(SmartRouteRequest(
        snapshot=result.snapshot, signature=result.signature, route_limit=100,
    ))
    assert provider.routes == 50 and provider.searches == searches
    assert expanded.coverage.routed == 50
    assert all(row.route.source == "fixture" for row in expanded.ranking.results)


def test_geometric_on_route_estimate_preserves_provider_baseline():
    from gaswise.contracts.common import Route
    from gaswise.domain.pricing.route_estimates import estimate_route

    origin, destination = Point(lat=34, lng=-118), Point(lat=35, lng=-118)
    baseline = Route(distance_meters=150000, duration_seconds=9000, source="fixture")
    estimate = estimate_route(origin, destination, Point(lat=34.5, lng=-117.8), baseline)
    assert estimate.distance_meters > baseline.distance_meters
    assert estimate.duration_seconds > baseline.duration_seconds
    assert estimate.source == "straight_line_estimate"


async def test_price_refresh_preserves_precise_routes_and_source_query_options():
    from gaswise.contracts.smart import SmartPriceRefresh
    provider = CountingProvider()
    service = SmartService(b"test","demo",demo=provider)
    first = await service.search(SmartSearch(origin=Point(lat=34,lng=-118),calculate_routes=True,route_limit=2,discovery_tiles=7,gasbuddy_page_limit=3))
    calls = provider.routes
    refreshed = await service.refresh_prices(SmartPriceRefresh(snapshot=first.snapshot,signature=first.signature,options=RankOptions(gallons=20)))
    assert provider.routes == calls
    assert refreshed.snapshot.routes == first.snapshot.routes
    assert refreshed.snapshot.routes_checked_at == first.snapshot.routes_checked_at
    assert refreshed.snapshot.acquisition_options == first.snapshot.acquisition_options
    assert refreshed.snapshot.query.gallons == 20
    assert refreshed.ranking.results
    service.verify(refreshed.snapshot,refreshed.signature)


async def test_price_refresh_renews_routes_only_after_independent_route_expiry():
    from gaswise.contracts.smart import SmartPriceRefresh
    provider = CountingProvider()
    service = SmartService(b"test","demo",demo=provider)
    first = await service.search(SmartSearch(origin=Point(lat=34,lng=-118),calculate_routes=True,route_limit=1))
    first.snapshot.routes_checked_at = datetime.now(UTC)-timedelta(minutes=16)
    # Expire only the independent route clock; the signed request itself is still valid.
    for key in list(service.cache.entries):
        service.cache.entries.pop(key)
    calls = provider.routes
    refreshed = await service.refresh_prices(SmartPriceRefresh(snapshot=first.snapshot,signature=service.sign(first.snapshot)))
    assert provider.routes > calls
    assert refreshed.snapshot.routes_checked_at > first.snapshot.routes_checked_at
    assert refreshed.ranking.results


@pytest.mark.parametrize('progressive', [False, True])
async def test_waze_login_failure_keeps_other_sources_and_ranking(progressive):
    class RejectedWaze:
        async def stations(self, query, *, all_fuels=False):
            raise ProviderError('waze_reauthentication_required')
    service = SmartService(b'test', 'prices_only', maps_web=MapsInventory(), waze=RejectedWaze(), router=CountingProvider())
    query = SmartSearch(origin=Point(lat=34, lng=-118), fuel_type='premium',
                        calculate_routes=True, allow_unknown_payment=True)
    try:
        if progressive:
            job = await service.start_progressive_search(query)
            await asyncio.gather(*service.progressive_tasks)
            state = await service.poll_progressive_search(job.job_id)
            assert state.status == 'complete'
            result = state.result
        else:
            result = await service.search(query)
        assert result is not None
        assert any(row.source == 'google_maps_web' for row in result.snapshot.stations)
        assert result.ranking is not None and result.ranking.results
        statuses = {row.source: row.status for row in result.snapshot.source_statuses}
        assert statuses['google_maps_web'] == 'ok' and statuses['waze'] == 'unavailable'
    finally:
        await service.close()
