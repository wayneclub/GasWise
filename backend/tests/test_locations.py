import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from gaswise.api.locations import LocationQuery, resolve_location
from gaswise.api.operations import OperationRunner
from gaswise.domain.ports import ProviderError
from gaswise.providers.geocoding import LocationProvider
from gaswise.providers.google.maps_web import MapsWebProvider


def row(identifier='zip', country='US', lat=34.0390107):
    data = [None] * 260
    data[9] = [None, None, lat, -118.2672801]
    data[10] = '0x1:0x2'
    data[11] = 'Los Angeles, CA 90015'
    data[78] = identifier
    data[183] = [None, [None, None, None, 'Los Angeles', None, 'California', country]]
    return data

async def test_maps_web_location_request_and_cache_never_call_places():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == 'www.google.com'
        assert request.url.path == '/search'
        assert request.url.params['q'] == '90015, United States'
        assert request.url.params['tbm'] == 'map'
        assert 'X-Goog-Api-Key' not in request.headers
        return httpx.Response(200, text=")]}'\n" + json.dumps([[row()]]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LocationProvider(MapsWebProvider(client))
        services = SimpleNamespace(locations=provider)
        result = await resolve_location(LocationQuery(text='90015'), services, OperationRunner(1))
        again = await resolve_location(LocationQuery(text='90015'), services, OperationRunner(1))
    assert result == again
    assert result.source == 'google_maps_web'
    assert result.candidates[0].location.lat == 34.0390107
    assert len(calls) == 1

async def test_location_missing_provider():
    with pytest.raises(HTTPException) as missing:
        await resolve_location(LocationQuery(text='90015'), SimpleNamespace(locations=None), OperationRunner(1))
    assert missing.value.status_code == 503

@pytest.mark.parametrize('status,body,code', [(429, '', 'google_maps_web_rate_limited'), (403, '', 'google_maps_web_blocked_or_redirected'), (200, '<html>challenge</html>', 'google_maps_web_unexpected_response')])
async def test_web_failures_have_no_fallback(status, body, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=body)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match=code):
            await LocationProvider(MapsWebProvider(client)).search('90015')
    assert len(calls) == 1

def test_location_parser_rejects_unknown_country_and_invalid_coordinates():
    malformed = row('missing')
    malformed[9] = None
    data = [row(), row(), row('foreign', 'CA'), row('unknown', None), row('bad', lat=100), malformed]
    parsed = LocationProvider.parse(data)
    assert len(parsed) == 1
    assert parsed[0]['id'] == 'zip'

async def test_invalid_private_session_stops_before_network(tmp_path):
    calls = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: calls.append(request))) as client:
        with pytest.raises(ProviderError):
            await LocationProvider(MapsWebProvider(client, tmp_path/'missing.json')).search('90015')
    assert calls == []
