import json

import httpx
import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.sources import GooglePriceSearch, MapsWebSearch
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.shared_cache import background_acquisition, collection_attempt
from gaswise.providers.google.maps_web import MapsWebProvider
from gaswise.providers.storage.request_budget import RequestBudget
from gaswise.providers.waze.provider import WazeProvider
from tests.providers.google.test_maps_web import record
from tests.providers.waze.test_waze import fuel_response


class Store:
    def __init__(self):
        self.calls = []
        self.cooldowns = []

    async def consume(self, source, limit, **kwargs):
        self.calls.append((source, kwargs))

    async def cooldown(self, source, seconds):
        self.cooldowns.append(source)


async def exercise(source, tmp_path, handler, *, background=True, login=False):
    store = Store()
    budget = RequestBudget(store, {source: 10})
    bg = background_acquisition.set(background)
    trace = {}
    token = collection_attempt.set(trace)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            if source == 'maps':
                provider = MapsWebProvider(client)
                provider.request_budget = budget
                result = await provider.prices(MapsWebSearch(origin=Point(lat=34.0347, lng=-118.2611), detail_limit=0))
                assert result.stations
            else:
                session = tmp_path / 'session.json'
                session.write_text(json.dumps({'uid': 'private-uid'}))
                login_file = tmp_path / 'login.bin'
                login_file.write_bytes(b'private-login')
                provider = WazeProvider(client, session, login_file, auto_login=False)
                provider.request_budget = budget
                if login:
                    provider.auto_login = True
                    await provider.login()
                else:
                    result = await provider.stations(GooglePriceSearch(origin=Point(lat=34.0833736, lng=-118.3008564), fuel_type='premium'))
                    assert result
        return store, trace
    finally:
        collection_attempt.reset(token)
        background_acquisition.reset(bg)


def success(source):
    if source == 'maps':
        return httpx.Response(200, text=")]}'\n" + json.dumps([record()]))
    return httpx.Response(200, content=fuel_response(), headers={'content-type': 'application/x-protobuf'})


@pytest.mark.parametrize('source', ['maps', 'waze'])
@pytest.mark.parametrize('error_kind', [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError,
                                       httpx.ReadTimeout, httpx.RemoteProtocolError])
async def test_batch_recovers_one_transient_connection_failure_with_each_request_budgeted(source, error_kind, tmp_path, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise error_kind('private-cookie-and-url', request=request)
        return success(source)

    store, trace = await exercise(source, tmp_path, handler)
    assert len(calls) == len(store.calls) == trace['http_requests'] == 2
    assert not store.cooldowns
    assert error_kind.__name__ in caplog.text
    assert 'private-cookie-and-url' not in caplog.text
    assert 'private-uid' not in caplog.text


@pytest.mark.parametrize('source', ['maps', 'waze'])
@pytest.mark.parametrize('background', [True, False])
async def test_persistent_transport_failure_is_bounded_and_keeps_original_public_error(source, background, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('private-cookie-and-url', request=request)

    with pytest.raises(ProviderError, match='google_maps_web_unavailable|waze_upstream_unavailable'):
        await exercise(source, tmp_path, handler, background=background)
    assert len(calls) == (2 if background else 1)


@pytest.mark.parametrize('source', ['maps', 'waze'])
@pytest.mark.parametrize('status', [403, 429, 503])
async def test_http_rejections_are_never_retried(source, status, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    with pytest.raises(ProviderError):
        await exercise(source, tmp_path, handler)
    assert len(calls) == 1


async def test_waze_login_transport_failure_is_not_replayed(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError('private-login', request=request)

    with pytest.raises(ProviderError, match='waze_upstream_unavailable'):
        await exercise('waze', tmp_path, handler, login=True)
    assert len(calls) == 1


async def test_retry_cannot_bypass_exhausted_shared_budget(tmp_path, monkeypatch):
    calls = []
    original = Store.consume

    async def limited(self, source, limit, **kwargs):
        await original(self, source, limit, **kwargs)
        if len(self.calls) == 2:
            raise ProviderError('maps_background_daily_budget_exhausted')

    monkeypatch.setattr(Store, 'consume', limited)

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError('private', request=request)

    with pytest.raises(ProviderError, match='maps_background_daily_budget_exhausted'):
        await exercise('maps', tmp_path, handler)
    assert len(calls) == 1


async def test_retry_stays_on_original_lane_even_if_health_changes(tmp_path):
    from gaswise.domain.pricing.shared_cache import collection_egress_key
    from gaswise.providers.http.batch_transport import source_request
    from gaswise.providers.http.egress_pool import PooledHTTPClient

    health = tmp_path / 'health.json'
    health.write_text('{"unavailable_lanes": []}')
    calls = []

    def factory(proxy):
        def handler(request):
            calls.append(proxy)
            if len(calls) == 1:
                health.write_text('{"unavailable_lanes": [0, 1]}')
                raise httpx.ConnectError('private', request=request)
            return httpx.Response(200)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    pool = PooledHTTPClient(['http://a:8888', 'http://b:8888'], client_factory=factory, health_file=health)
    bg = background_acquisition.set(True)
    key = collection_egress_key.set('batch-transport-pinned-regression')
    try:
        response = await source_request(pool, 'get', 'https://www.google.com/search', source='maps', read_only=True)
        assert response.status_code == 200
        assert len(calls) == 2 and calls[0] == calls[1]
    finally:
        collection_egress_key.reset(key)
        background_acquisition.reset(bg)
        await pool.aclose()
