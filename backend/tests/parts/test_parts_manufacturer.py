from types import SimpleNamespace

import pytest

from gaswise.providers.parts.manufacturer import (
    ManufacturerParts,
    assess_wix_applications,
    wix_candidates,
)
from tests.support.paths import FIXTURES as FIXTURE_ROOT

FIX = FIXTURE_ROOT / "manufacturer"


def vehicle(**changes):
    return SimpleNamespace(
        **dict(
            dict(
                year=2018, make="Mercedes-Benz", model="E-Class", trim="E400", engine_liters=3.0, cylinders=6
            ),
            **changes,
        )
    )


def test_crossreference_exact_brand_and_number():
    html = (FIX / "wix-mann.html").read_text()
    rows = wix_candidates(html, "Mann-Filter", ["HU7025Z"])
    assert {x["part_number"] for x in rows} == {"57059"}
    assert rows[0]["relation"] == "interchange_candidate"
    assert not wix_candidates(html, "Bosch", ["HU7025Z"])
    assert not wix_candidates(html, "Mann-Filter", ["HU7025"])


@pytest.mark.parametrize(
    "changes", [dict(year=2021), dict(trim="C300"), dict(cylinders=4), dict(engine_liters=3.5)]
)
def test_wrong_vehicle_does_not_match(changes):
    result = assess_wix_applications((FIX / "wix-applications.html").read_text(), "57059", vehicle(**changes))
    assert result["status"] == "no_match"


def test_full_live_application_fixture_matches():
    result = assess_wix_applications((FIX / "wix-applications.html").read_text(), "57059", vehicle())
    assert result["status"] == "matched"
    assert "cylinders" in result["matched_fields"]
    assert assess_wix_applications("<h1>challenge</h1>", "57059", vehicle())["status"] == "unavailable"


@pytest.mark.parametrize("engine", ["V6 3.0L with center tube", "3.0L", "V6 3.0L engine number up to 999"])
def test_restrictions_never_guess(engine):
    html = (
        '<h1>Applications for part 57059</h1><table id="gvPartapps"><tr>'
        + "".join("<td>" + x + "</td>" for x in ["", "Mercedes Benz", "E400", "2018 - 2018", engine])
        + "</tr></table>"
    )
    assert assess_wix_applications(html, "57059", vehicle())["status"] == "conditional"


@pytest.mark.asyncio
async def test_dynamic_candidate_assessment():
    class Reader:
        async def read(self, url, **kwargs):
            if "Exactmatch" in url:
                assert kwargs["params"]["PartNo"] == "HU7025Z"
                return (FIX / "wix-mann.html").read_text()
            assert kwargs["params"] == {"Part": "57059"}
            return (FIX / "wix-applications.html").read_text()

    rows = await ManufacturerParts(Reader()).assess(
        dict(brand="Mann-Filter", identifiers=["HU7025Z"]), vehicle()
    )
    assert rows[0]["status"] == "matched"
    assert rows[0]["source"] == "manufacturer"
    assert rows[0]["brand"] == "WIX"
    assert rows[0]["reference_part_number"] == "HU 7025 z"


@pytest.mark.asyncio
async def test_multiple_replacements_are_ambiguous():
    class Reader:
        async def read(self, url, **kwargs):
            return (
                '<table id="gvPL">'
                + "".join(
                    "<tr><td></td><td>123</td><td>Bosch</td><td>" + p + "</td></tr>" for p in ["456", "789"]
                )
                + "</table>"
            )

    rows = await ManufacturerParts(Reader()).assess(dict(brand="Bosch", identifiers=["123"]), vehicle())
    assert rows[0]["status"] == "ambiguous"
