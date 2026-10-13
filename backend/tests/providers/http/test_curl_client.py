import json

import pytest

from gaswise.contracts.sources import GasBuddySearch
from gaswise.providers.gasbuddy.http_session import GasBuddyHTTPSession
from gaswise.providers.http.curl_client import CurlHTTPClient


async def test_guest_session_and_csrf_survive_shared_transport_without_disk_cookies():
    created = []

    class Response:
        status_code = 200
        headers = {}

        def __init__(self, data):
            self.data = data

        async def aiter_content(self):
            yield self.data

        async def aclose(self):
            pass

    class Session:
        def __init__(self, **options):
            assert options["trust_env"] is False
            created.append(self)
            self.guest, self.closed = False, False

        async def get(self, url, **options):
            assert options["discard_cookies"] is False
            self.guest = True
            return Response(b'window.gbcsrf = "fixture-csrf";')

        async def post(self, url, **options):
            assert self.guest
            assert options["headers"]["gbcsrf"] == "fixture-csrf"
            return Response(
                json.dumps(
                    {
                        "data": {
                            "locationBySearchTerm": {"stations": {"results": [], "cursor": {"next": None}}}
                        }
                    }
                ).encode()
            )

        async def close(self):
            self.closed = True

    worker = GasBuddyHTTPSession(
        client_factory=lambda: CurlHTTPClient(
            allowed_hosts={"www.gasbuddy.com"}, session_factory=Session, preserve_cookies=True
        )
    )
    try:
        _, data = await worker.snapshot(GasBuddySearch(postal_code="90015"), "", 3)
        assert data["results"] == []
        assert len(created) == 1
    finally:
        await worker.close()
    assert created[0].closed


async def test_shared_transport_rejects_unauthorized_destination_before_network():
    client = CurlHTTPClient(allowed_hosts={"www.gasbuddy.com"})
    with pytest.raises(ValueError, match="curl_host_not_allowed"):
        await client.post("https://example.com/", json={"query": "fixture"})


def test_fixed_proxy_reaches_curl_session_without_trusting_environment():
    options = {}
    CurlHTTPClient(
        allowed_hosts={"www.gasbuddy.com"},
        session_factory=lambda **kw: options.update(kw),
        proxy="http://gluetun:8888",
    ).new_session()
    assert options["proxy"] == "http://gluetun:8888"
    assert options["trust_env"] is False
