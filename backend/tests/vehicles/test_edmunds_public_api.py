import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.main import create_app
from gaswise.providers.vehicles.specifications import SpecificationProvider, parse_edmunds_style
from tests.support.paths import FIXTURES as FIXTURE_ROOT
from tests.support.specification_assessment import EPA, HERTZ, HERTZ_URL, raw_profile
from tests.support.vehicle_requirements_2021 import PROFILES

FIXTURES = FIXTURE_ROOT


def fixture(make, model, suffix):
    return json.loads((FIXTURES / f"edmunds-{make}-{model}-2021-{suffix}.json").read_text())


class PublicFixture:
    def __init__(self, make="toyota", model="camry"):
        self.make, self.model = make, model
        self.meta = fixture(make, model, "metadata")
        self.data = fixture(make, model, "specs")
        self.calls = []

    async def read(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "edmunds.com" in url:
            assert kwargs["headers"] == {
                "Accept": "application/json",
                "Referer": f"https://www.edmunds.com/{self.make}/{self.model}/2021/features-specs/",
            }
            return json.dumps(self.meta if "modelYears" in url else self.data)
        if "getInventoryAndFacets" in url:
            return json.dumps(
                {"inventory": [{"year": 2021, "make": "Toyota", "model": "Camry", "link": HERTZ_URL}]}
            )
        return HERTZ


@pytest.mark.parametrize(
    "make,model,vehicle,grade,requirement",
    [
        ("toyota", "camry", EPA[43305], "regular", "unspecified"),
        ("toyota", "camry", EPA[43302], "regular", "unspecified"),
        ("bmw", "x3", PROFILES[42899], "premium", "recommended"),
        ("bmw", "m4", PROFILES[43560], "premium", "required"),
    ],
)
async def test_dynamic_metadata_and_config_match(make, model, vehicle, grade, requirement):
    public = PublicFixture(make, model)
    async with httpx.AsyncClient() as client:
        result = await SpecificationProvider(client, public).edmunds(vehicle)
    assert result.status == "matched"
    assert (result.fuel_grade, result.requirement) == (grade, requirement)
    assert result.numeric_octane_aki is None
    assert len(public.calls) == 2


@pytest.mark.parametrize("change", [{"year": 2020}, {"makeNiceId": "honda"}, {"modelNiceId": "accord"}])
async def test_metadata_echo_mismatch_rejected_before_styles(change):
    public = PublicFixture()
    public.meta["results"][0].update(change)
    async with httpx.AsyncClient() as client:
        result = await SpecificationProvider(client, public).edmunds(EPA[43305])
    assert result.status == "mismatch" and len(public.calls) == 1


async def test_dataset_echo_and_style_membership_fail_closed():
    for changed in ("dataset", "membership"):
        public = PublicFixture()
        if changed == "dataset":
            public.data["$dataset"] = public.data["$dataset"].replace("2021", "2020")
        else:
            public.meta["results"][0]["styles"] = [{"id": 1}]
        async with httpx.AsyncClient() as client:
            result = await SpecificationProvider(client, public).edmunds(EPA[43305])
        assert result.status != "matched"


def test_phev_wrong_drive_and_wrong_trim_excluded():
    rows = fixture("bmw", "x3", "specs")["results"]
    results = {row["name"]: parse_edmunds_style(row, PROFILES[42899], "test") for row in rows}
    assert sum(r.status == "matched" for r in results.values()) == 1
    assert next(r for n, r in results.items() if "xDrive30e" in n).status == "mismatch"
    rows = fixture("bmw", "m4", "specs")["results"]
    assert parse_edmunds_style(rows[0], PROFILES[43560], "test").status == "mismatch"
    assert parse_edmunds_style(rows[1], PROFILES[43560], "test").status == "matched"


async def test_same_physical_configuration_conflicting_labels_are_ambiguous():
    public = PublicFixture()
    row = copy.deepcopy(public.data["results"][0])
    row["features"]["standard"]["Fuel"][0]["value"] = "Premium unleaded (required)"
    public.data["results"].append(row)
    async with httpx.AsyncClient() as client:
        result = await SpecificationProvider(client, public).edmunds(EPA[43305])
    assert result.status == "ambiguous"


async def test_empty_metadata_no_guessed_default_style():
    public = PublicFixture()
    public.meta = {}
    async with httpx.AsyncClient() as client:
        result = await SpecificationProvider(client, public).edmunds(EPA[43305])
    assert result.status == "unavailable" and len(public.calls) == 1


def test_real_main_wiring_three_source_agreement(monkeypatch):
    public = PublicFixture()
    monkeypatch.setattr("gaswise.app.bootstrap.PublicHTTP", lambda: public)
    original = httpx.AsyncClient

    def handle(request):
        assert request.url.host == "www.fueleconomy.gov"
        return httpx.Response(200, json=raw_profile(EPA[43305]))

    monkeypatch.setattr(
        "gaswise.app.bootstrap.httpx.AsyncClient",
        lambda *a, **kw: original(transport=httpx.MockTransport(handle)),
    )
    with TestClient(
        create_app(
            Settings(
                _env_file=None, vehicle_specifications_enabled=True, vehicle_specifications_transport="curl"
            )
        )
    ) as client:
        response = client.post("/v1/vehicles/fuel-assessment", json={"vehicle_id": 43305})
    data = response.json()
    assert response.status_code == 200
    rows = data["vehicle"]["fuel_recommendation"]["specification_evidence"]
    assert [r["status"] for r in rows] == ["matched", "matched", "matched"]
    assert data["vehicle"]["fuel_recommendation"]["assessment_status"] == "agreement"
    assert data["vehicle"]["fuel_recommendation"]["manufacturer_requirement_verified"] is False
