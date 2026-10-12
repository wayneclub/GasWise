import json

import pytest

from gaswise.providers.http.oreilly_session import OReillyHTTPSession, browser_verification, csrf_from_html


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code, self.closed = body, status, False

    async def aiter_content(self):
        yield self.body.encode()

    async def aclose(self):
        self.closed = True


async def test_owned_anonymous_session_and_server_csrf_never_replay_external_credentials():
    sessions = []

    class Session:
        def __init__(self, **kwargs):
            self.calls = []
            self.responses = []
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            assert kwargs["auth"] is None and not kwargs["allow_redirects"]
            body = (
                "window._ost={'csrfToken':'synthetic-server-value'};" if url.endswith("/") else '{"data":[]}'
            )
            response = Response(body)
            self.responses.append(response)
            return response

    for _ in range(2):
        owned = OReillyHTTPSession(Session)
        async with owned as reader:
            await reader.read(
                "https://www.oreillyauto.com/interchange/getManufacturers",
                json_body={},
                headers={"Cookie": "private", "Authorization": "private", "X-CSRF-TOKEN": "external-token"},
            )
            assert reader.stages == ["anonymous_session_csrf"]
        assert owned.csrf is None and owned.session is None
    assert len(sessions) == 2 and all(len(s.calls) == 2 for s in sessions)
    headers = sessions[0].calls[1][2]["headers"]
    assert headers["X-CSRF-TOKEN"] == "synthetic-server-value"
    assert "Cookie" not in headers and "Authorization" not in headers
    assert all(r.closed for s in sessions for r in s.responses)


@pytest.mark.parametrize("status", [200, 429])
async def test_challenge_is_not_catalog_data_even_for_http200(status):
    class Session:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, *args, **kwargs):
            return Response(json.dumps({"cpr_chlge": "true", "t": 1}), status)

    async with OReillyHTTPSession(Session) as reader:
        assert await reader.read("https://www.oreillyauto.com/search") is None
        assert reader.failure == "browser_verification_required"
        with pytest.raises(ValueError):
            await reader.read("https://evil.com/secret")


def test_csrf_and_protection_classification():
    assert (
        csrf_from_html("window._ost={'csrfToken':'fresh-server-issued-token'}") == "fresh-server-issued-token"
    )
    assert csrf_from_html("Robot check") is None
    assert browser_verification('<img class="scf-akamai-logo">Powered and protected by')
    assert not browser_verification('{"data":[]}')


@pytest.mark.parametrize("mismatch", [None, "vehicleId", "engineId", "baseVehicleId", "vehicleTypeId"])
async def test_public_catalog_cookie_selection_requires_exact_server_confirmation(mismatch):
    from types import SimpleNamespace

    from curl_cffi.requests import Cookies

    selected = {
        "baseVehicleId": "144122",
        "vehicleId": "144122-39089-304121",
        "engineId": "304121",
        "vehicleTypeId": 1,
    }
    if mismatch:
        selected[mismatch] = "wrong"

    class Reader(OReillyHTTPSession):
        async def read(self, url, **kwargs):
            assert url.endswith("/header/data") and kwargs["json_body"] == {}
            return json.dumps({"selectedVehicle": selected})

    reader = Reader()
    reader.session = SimpleNamespace(cookies=Cookies())
    result = await reader.select_vehicle(base_vehicle_id="144122", submodel_id="39089", engine_id="304121")
    assert reader.session.cookies.get("ECV") == "1-144122-39089-304121"
    assert reader.session.cookies.get("EGV") == "1-144122-39089-304121"
    if mismatch:
        assert result is None and reader.selected_vehicle is None
        assert reader.failure == "selected_vehicle_not_verified"
    else:
        assert result == selected
        assert reader.stages == ["public_catalog_selection_verified"]


async def test_catalog_selection_rejects_cookie_injection():
    from types import SimpleNamespace

    from curl_cffi.requests import Cookies

    reader = OReillyHTTPSession()
    reader.session = SimpleNamespace(cookies=Cookies())
    with pytest.raises(ValueError, match="invalid_vehicle_catalog_identifier"):
        await reader.select_vehicle(
            base_vehicle_id="144122; other=1", submodel_id="39089", engine_id="304121"
        )
    assert not list(reader.session.cookies)


@pytest.mark.parametrize("case", ["valid", "mismatch", "ambiguous", "missing_engine", "invalid_id"])
async def test_vin_configuration_is_dynamic_and_never_exposes_vin(case):
    row = {
        "year": "2021",
        "makeId": "123",
        "make": "Toyota",
        "modelId": "456",
        "model": "Camry",
        "subModel": [{"id": 10, "value": "LE"}],
        "engine": [{"id": 20, "value": "I4 - 2.5L"}],
    }
    if case == "mismatch":
        row["model"] = "Corolla"
    if case == "missing_engine":
        row["engine"] = []
    if case == "invalid_id":
        row["makeId"] = "not-an-id"
    data = {"vinIsValid": True, "vins": [row, row] if case == "ambiguous" else [row]}

    class Reader(OReillyHTTPSession):
        async def read(self, url, **kwargs):
            assert "/vehicle/vin/" in url
            return json.dumps(data)

    reader = Reader()
    vin = "1HGCM82633A004352"
    result = await reader.vin_configuration(vin, year=2021, make="TOYOTA", model="Camry")
    if case == "valid":
        assert result["makeId"] == "123" and result["modelId"] == "456"
        assert result["engine_options"] == [{"id": "20", "description": "I4 - 2.5L"}]
        assert reader.stages == ["native_vin_configuration"]
        assert vin not in json.dumps(result)
    else:
        assert result is None and reader.failure
        assert not reader.stages


async def test_native_typeahead_uses_only_homepage_public_key_and_clears_it():
    calls = []

    class Session:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/"):
                return Response("window._ost={'config':{'apiKey':'synthetic-public-search-key'}}")
            return Response(json.dumps({"suggestions": [{"suggestion": "cabin air filter"}]}))

    reader = OReillyHTTPSession(Session)
    async with reader:
        result = await reader.search_suggestions(
            "cabin air filter", year=2018, make="Mercedes-Benz", model="E400", market_id=25
        )
        assert result == ["cabin air filter"]
        await reader.read("https://www.oreillyauto.com/search", headers={"x-api-key": "external"})
    assert calls[1][1]["headers"]["x-api-key"] == "synthetic-public-search-key"
    assert "x-api-key" not in calls[2][1]["headers"]
    assert reader._public_search_key is None
