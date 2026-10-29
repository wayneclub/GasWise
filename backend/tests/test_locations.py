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


def row(identifier='zip', country='US', lat=34.0390107, name='Los Angeles, CA 90015', business=None):
    data = [None] * 260
    data[9] = [None, None, lat, -118.2672801]
    data[10] = '0x1:0x2'
    data[11] = name
    data[78] = identifier
    # Observed: businesses carry a SearchResult type; cities and areas carry None.
    data[88] = [None, business and f'SearchResult.TYPE_{business}', None, name]
    data[183] = [None, [None, None, None, 'Los Angeles', None, 'California', country]]
    return data

def maps_response(*rows):
    return httpx.Response(200, text=")]}'\n" + json.dumps([list(rows)]))

async def lookup(handler, *texts):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        services = SimpleNamespace(locations=LocationProvider(MapsWebProvider(client)))
        return [await resolve_location(LocationQuery(text=text), services, OperationRunner(1)) for text in texts]

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

async def test_free_text_city_name_resolves_with_one_request():
    queries = []
    def handler(request):
        queries.append(request.url.params['q'])
        return maps_response(row('nyc', name='New York', lat=40.71))
    [result] = await lookup(handler, 'new york')
    assert queries == ['new york']
    assert [c.label for c in result.candidates] == ['New York']
    assert result.reason is None

async def test_case_and_spacing_variants_share_one_lookup():
    queries = []
    def handler(request):
        queries.append(request.url.params['q'])
        return maps_response(row('nyc', name='New York', lat=40.71))
    first, second = await lookup(handler, '  New   York ', 'new york')
    assert queries == ['New York']
    assert first == second

async def test_two_letter_abbreviation_is_a_valid_query():
    queries = []
    def handler(request):
        queries.append(request.url.params['q'])
        return maps_response(row('nyc', name='New York', lat=40.71))
    [result] = await lookup(handler, 'NY')
    assert queries == ['NY']
    assert result.candidates[0].label == 'New York'

async def test_business_top_hit_retries_us_scoped_and_prefers_the_place():
    # Observed: "new york, new york" returns the Las Vegas casino hotel, and a
    # lone candidate is applied without asking, so the user lands in Nevada.
    queries = []
    def handler(request):
        queries.append(request.url.params['q'])
        if request.url.params['q'].endswith(', United States'):
            return maps_response(row('nyc', name='New York', lat=40.71))
        return maps_response(row('casino', name='New York-New York Hotel & Casino', lat=36.10, business='LODGING'))
    [result] = await lookup(handler, 'new york, new york')
    assert queries == ['new york, new york', 'new york, new york, United States']
    assert [c.id for c in result.candidates] == ['nyc']

async def test_business_search_keeps_business_results_when_retry_finds_no_place():
    queries = []
    def handler(request):
        queries.append(request.url.params['q'])
        return maps_response(row('costco', name='Costco Wholesale', business='STORE'))
    [result] = await lookup(handler, 'costco burbank')
    assert len(queries) == 2
    assert [c.id for c in result.candidates] == ['costco']

async def test_foreign_only_results_report_unsupported_area():
    queries = []
    def handler(request):
        queries.append(request.url.params['q'])
        return maps_response(row('taipei', 'TW', name='Taipei City', lat=25.03))
    [result] = await lookup(handler, 'taipei')
    assert queries == ['taipei']
    assert result.candidates == []
    assert result.reason == 'unsupported_area'

async def test_no_results_have_no_reason():
    [result] = await lookup(lambda request: maps_response(), 'zzqx')
    assert result.candidates == []
    assert result.reason is None

async def test_native_language_search_passes_hl_and_resolves_local_labels():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.params['hl'] == 'zh-TW'
        return maps_response(row('la_dt', name='洛杉磯市中心', lat=34.05))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        services = SimpleNamespace(locations=LocationProvider(MapsWebProvider(client)))
        result = await resolve_location(LocationQuery(text='downtown la', locale='zh-TW'), services, OperationRunner(1))
    assert len(calls) == 1
    assert result.candidates[0].label == '洛杉磯市中心'

async def test_location_search_retries_once_on_temporary_transport_failure():
    attempts = [0]
    def handler(request):
        attempts[0] += 1
        if attempts[0] == 1:
            raise httpx.ConnectError('connection failed on exit 1')
        return maps_response(row('la_dt', name='Downtown LA', lat=34.05))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        services = SimpleNamespace(locations=LocationProvider(MapsWebProvider(client)))
        result = await resolve_location(LocationQuery(text='downtown la'), services, OperationRunner(1))
    assert attempts[0] == 2
    assert result.candidates[0].id == 'la_dt'
