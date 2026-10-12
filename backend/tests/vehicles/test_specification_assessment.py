import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.domain.vehicles.fuel_policy import resolve_fuel_query
from gaswise.domain.vehicles.requirements import manufacturer_fuel_requirement
from gaswise.domain.vehicles.specification_assessment import combine_specifications
from gaswise.main import create_app
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.providers.vehicles.specifications import SpecificationProvider, parse_specs
from gaswise.services.pricing.search import SearchService
from tests.support.comparison import Prices, quote
from tests.support.specification_assessment import (
    EDM_URL as EDM_URL,
)
from tests.support.specification_assessment import (
    EPA as EPA,
)
from tests.support.specification_assessment import (
    FIXTURES as FIXTURES,
)
from tests.support.specification_assessment import (
    HERTZ as HERTZ,
)
from tests.support.specification_assessment import (
    HERTZ_URL as HERTZ_URL,
)
from tests.support.specification_assessment import (
    observation as observation,
)
from tests.support.specification_assessment import (
    raw_profile as raw_profile,
)
from tests.support.specification_assessment import (
    specs_html as specs_html,
)
from tests.support.vehicle_requirements_2021 import PROFILES


def test_actual_hertz_inline_fixture_matches_only_correct_engine():
    result = parse_specs(HERTZ, EPA[43305], "hertz", HERTZ_URL)
    assert result.status == "matched"
    assert result.fuel_grade == "regular"
    assert result.numeric_octane_aki is None
    assert parse_specs(HERTZ, EPA[43302], "hertz", HERTZ_URL).status == "mismatch"


@pytest.mark.parametrize(
    "label,requirement",
    [
        ("Regular unleaded", "unspecified"),
        ("Premium unleaded (recommended)", "recommended"),
        ("Premium unleaded (required)", "required"),
    ],
)
def test_edmunds_labels_preserve_required_vs_recommended(label, requirement):
    e = parse_specs(specs_html(fuel=label), EPA[43305], "edmunds", EDM_URL)
    assert e.status == "matched"
    assert e.requirement == requirement
    assert e.numeric_octane_aki is None


@pytest.mark.parametrize(
    "changes",
    [
        {"year": 2020},
        {"engine": "3.5"},
        {"drive": "All wheel drive"},
        {"make": "Honda"},
        {"cylinders": 6},
        {"transmission": "6-speed manual"},
    ],
)
def test_wrong_configuration_does_not_vote(changes):
    assert parse_specs(specs_html(**changes), EPA[43305], "edmunds", EDM_URL).status == "mismatch"


def test_matching_regular_sources_produce_estimate_not_fake_manufacturer_minimum():
    r = combine_specifications(EPA[43305], [observation(), observation(source="hertz", group="dealer_specs")])
    assert r.recommended_octane_aki == 87
    assert r.minimum_octane_aki is None
    assert r.source == "specification_consensus"
    assert not r.manufacturer_requirement_verified
    assert r.assessment_status == "agreement"


def test_shared_source_groups_do_not_gain_more_votes():
    # Duplicate dealership observations alone do not establish agreement with a conflicting EPA grade.
    r = combine_specifications(EPA[43305], [observation("premium", source="hertz", group="dealer_specs")] * 5)
    assert r.assessment_status == "conflict"
    assert r.recommended_octane_aki is None
    assert r.minimum_octane_aki is None


def test_related_inventory_trim_cannot_match_selected_configuration():
    v = EPA[43302].model_copy(update={"model": "Camry TRD"})
    html = specs_html(engine="3.5", cylinders=6) + "<aside>Related inventory: Camry TRD</aside>"
    assert parse_specs(html, v, "edmunds", EDM_URL).status == "mismatch"


def test_premium_policy_remains_unverified_and_diesel_has_no_aki():
    v = PROFILES[42597].model_copy(deep=True)
    r = combine_specifications(v, [])
    assert r.recommended_octane_aki == 91
    assert r.minimum_octane_aki is None
    assert not r.manufacturer_requirement_verified
    diesel = EPA[43305].model_copy(update={"powertrain": "diesel", "fuel_type": "Diesel"})
    assert combine_specifications(diesel, []).recommended_octane_aki is None


def test_ford_recommended_premium_upgrade_does_not_turn_into_required_premium():
    r = combine_specifications(EPA[47167], [observation("premium", "recommended")])
    assert r.recommended_octane_aki == 87
    assert r.minimum_octane_aki is None
    assert r.assessment_status == "single_source"
    assert any("optional upgrade" in w for w in r.assessment_warnings)
    conflict = combine_specifications(EPA[47167], [observation("premium", "required")])
    assert conflict.assessment_status == "conflict"
    assert conflict.recommended_octane_aki is None
    v = EPA[47167].model_copy(deep=True)
    v.fuel_recommendation = conflict
    with pytest.raises(ProviderError, match="vehicle_fuel_specification_conflict"):
        resolve_fuel_query(Search(origin=quote().location), v)
    explicit = resolve_fuel_query(Search(origin=quote().location, fuel_type="premium", required_octane=91), v)
    assert explicit.required_octane == 91


def test_manufacturer_minimum_wins_for_x3_and_m4():
    for vid, minimum in [(42900, 89), (43559, 91)]:
        v = PROFILES[vid].model_copy(deep=True)
        v.fuel_recommendation = manufacturer_fuel_requirement(v)
        r = combine_specifications(v, [observation("regular")])
        assert r.assessment_status == "manufacturer_verified"
        assert r.minimum_octane_aki == minimum
        assert any("takes precedence" in w for w in r.assessment_warnings)


async def test_blocked_sources_are_single_source_and_negative_cached():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        provider = SpecificationProvider(c)
        first = await provider.observations(EPA[43305])
        second = await provider.observations(EPA[43305])
    assert len(calls) == 2
    assert all(e.status == "unavailable" for e in first + second)
    r = combine_specifications(EPA[43305], first)
    assert r.assessment_status == "single_source"
    assert r.recommended_octane_aki == 87
    assert any("not a multi-source" in w for w in r.assessment_warnings)


async def test_spec_reads_do_not_inherit_auth_cookies_or_follow_redirects():
    seen = []

    def handler(req):
        seen.append(req)
        assert "authorization" not in req.headers
        assert "cookie" not in req.headers
        assert "x-api-key" not in req.headers
        return httpx.Response(302, headers={"Location": "https://evil.example/"})

    async with httpx.AsyncClient(
        headers={"Authorization": "synthetic", "x-api-key": "synthetic"},
        cookies={"session": "synthetic"},
        auth=("synthetic", "synthetic"),
        transport=httpx.MockTransport(handler),
    ) as c:
        result = await SpecificationProvider(c).observations(EPA[43305])
    assert len(seen) == 2
    assert all(e.status == "unavailable" for e in result)


def test_malformed_inline_types_are_ambiguous_not_a_vehicle_api_failure():
    malformed = HERTZ.replace('"name":"Toyota"', '"name":123')
    assert parse_specs(malformed, EPA[43305], "hertz", HERTZ_URL).status == "ambiguous"


async def test_full_provider_assessment_and_ranking_uses_87_floor():
    calls = []

    def handler(req):
        calls.append(str(req.url))
        if req.url.host == "www.fueleconomy.gov":
            return httpx.Response(200, json=raw_profile(EPA[43305]))
        if req.url.host == "www.edmunds.com":
            return httpx.Response(200, text=specs_html())
        if req.url.path.endswith("used-cars-for-sale.htm"):
            return httpx.Response(200, text=f'<a href="{HERTZ_URL}">Camry</a>')
        return httpx.Response(200, text=HERTZ)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        catalog = VehicleProvider(c, SpecificationProvider(c))
        records = [
            quote(station_id=str(n), octane=n).model_copy(update={"fuel_type": "regular"})
            for n in [85, 87, 89]
        ]
        result = await SearchService(Prices(records), "google", catalog).search(
            Search(origin=records[0].location, vehicle_id=43305)
        )
        assert result.applied_octane_aki == 87
        assert {r.station.id for r in result.results} == {"87", "89"}
        v = await catalog.vehicle(43305)
        assert v.fuel_recommendation.assessment_status == "agreement"
        assert len(calls) == 4
        assert any("not verified manufacturer" in w for w in result.warnings)


def test_main_wiring_assessment_returns_estimate_and_unavailable_not_agreement(monkeypatch):
    def handler(req):
        if req.url.host == "www.fueleconomy.gov":
            return httpx.Response(200, json=raw_profile(EPA[43305]))
        return httpx.Response(403)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "gaswise.app.bootstrap.httpx.AsyncClient",
        lambda *a, **kw: original(transport=httpx.MockTransport(handler)),
    )
    s = Settings(_env_file=None, mode="demo", vehicle_specifications_enabled=True)
    with TestClient(create_app(s)) as client:
        response = client.post("/v1/vehicles/fuel-assessment", json={"vehicle_id": 43305})
    assert response.status_code == 200
    data = response.json()
    assert data["target_octane_aki"] == 87
    assert data["target_basis"] == "specification_estimate"
    assert data["hertz_status"] == "unavailable"
    assert data["vehicle"]["fuel_recommendation"]["assessment_status"] == "single_source"
