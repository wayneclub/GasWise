import httpx
import pytest

from gaswise.domain.ports import ProviderError
from gaswise.providers.pricing.aaa import AAAProvider
from gaswise.providers.pricing.aaa_http import AAAHTTP
from tests.support.paths import FIXTURES


def reader(*, status=200, chunks=None, challenge=False):
    calls = []

    class Response:
        status_code = status
        headers = {"cf-mitigated": "challenge", "set-cookie": "never-forward"} if challenge else {}
        closed = False

        async def aiter_content(self):
            for chunk in chunks or [(FIXTURES / "aaa.html").read_bytes()]:
                yield chunk

        async def aclose(self):
            self.closed = True

    response = Response()

    class Session:
        def __init__(self, **kwargs):
            assert "impersonate" not in kwargs
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            assert kwargs["discard_cookies"] is True
            assert kwargs["allow_redirects"] is False
            calls.append(url)
            return response

    return AAAHTTP(Session), response, calls


async def test_anonymous_standard_curl_preserves_page_provenance():
    http, response, calls = reader()
    snapshot = await AAAProvider(http).averages("CA")
    assert snapshot.price_as_of.isoformat() == "2026-10-09"
    assert snapshot.source_url == "https://gasprices.aaa.com/?state=CA"
    assert calls == [snapshot.source_url]
    assert response.closed


async def test_challenge_remains_unavailable_without_cookies():
    http, response, _ = reader(status=403, challenge=True)
    with pytest.raises(ProviderError, match="aaa_upstream_challenge"):
        await AAAProvider(http).averages("CA")
    assert response.closed


async def test_response_limit_closes_stream():
    http, response, _ = reader(chunks=[b"x" * 4_000_001])
    with pytest.raises(httpx.ReadError):
        await http.get("https://gasprices.aaa.com/?state=CA")
    assert response.closed


async def test_no_arbitrary_upstream():
    http, _, _ = reader()
    with pytest.raises(ValueError, match="aaa_host_not_allowed"):
        await http.get("https://example.com/")
