import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.domain.ports import ProviderError
from gaswise.main import create_app
from gaswise.providers.pricing.aaa import AAAProvider, parse_page
from tests.support.paths import FIXTURES as FIXTURE_ROOT

HTML = (FIXTURE_ROOT / "aaa.html").read_text()


def test_precision_regions_and_dates():
    published, regions = parse_page(HTML, "CA")
    assert published.isoformat() == "2026-10-09"
    assert [r.level for r in regions] == ["state", "metro"]
    assert regions[1].model_dump(mode="json")["prices"]["current"]["premium"] == "4.1234"
    with pytest.raises(ProviderError):
        parse_page("<html>challenge</html>", "CA")
    with pytest.raises(ProviderError):
        parse_page(HTML.replace("<td>$4.1234</td>", "", 1), "CA")


async def test_counties_and_http_failure():
    async def handler(request):
        if request.url.path == "/index.php":
            return httpx.Response(
                200,
                text='var cfg = {map_data: {"st1":{"name":"Alameda","comment":"$4.321"},"st2":{"name":"Alpine","comment":""}}, x: 1};',
            )
        return httpx.Response(
            200, text=HTML + '<script src="?premiumhtml5map_js_data=true&#038;map_id=7"></script>'
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AAAProvider(client).averages("CA")
        assert result.county_status == "available"
        assert result.regions[-1].prices["current"]["regular"] is None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        with pytest.raises(ProviderError, match="aaa_upstream_unavailable"):
            await AAAProvider(client).averages("CA")


def test_endpoint_auth_validation_and_serialization():
    with TestClient(create_app(Settings(api_token="test"))) as client:
        assert client.get("/v1/sources/aaa/averages").status_code == 401
        headers = {"Authorization": "Bearer test"}
        assert client.get("/v1/sources/aaa/averages?state=ZZ", headers=headers).status_code == 422

        async def averages(state):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200, text=HTML))
            ) as upstream:
                return await AAAProvider(upstream).averages(state)

        client.app.state.services.aaa.averages = averages
        response = client.get("/v1/sources/aaa/averages?state=ca", headers=headers)
        assert response.status_code == 200
        assert response.json()["state"] == "CA"
        assert response.json()["regions"][0]["prices"]["current"]["regular"] == "4.1234"
        assert response.headers["cache-control"] == "no-store"
