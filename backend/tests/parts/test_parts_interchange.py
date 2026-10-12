import json
from urllib.parse import urlencode

import pytest

from gaswise.contracts.parts import PartsEvidence, PartsRequest
from gaswise.providers.parts.autozone import AutoZoneParts
from gaswise.providers.parts.interchange import InterchangeHTML, discover_interchanges
from gaswise.providers.parts.oreilly import OReillyParts
from gaswise.services.parts.fitment import PartsProvider, retailer_cross_check
from tests.support.parts import URL, Decoder, amazon_html, catalog_html


def card(number="MGL57059", line="MGD", reference="HU7025Z"):
    source = "/search/cross-reference?" + urlencode(
        {"partNumber": reference, "manufacturerFilter": "Mann + Hummel"}
    )
    return (
        f'<article class="product product--interchange"><a href="{source}">Mann + Hummel</a>'
        f'<input id="compare{line}-{number}"><h3>MicroGard Oil Filter - {number}</h3>'
        f'<a href="/detail/c/microgard/microgard-oil-filter/mgd3/{number.lower()}">Filter</a></article>'
    )


class Reader:
    async def read(self, url, **kwargs):
        if url.endswith("/interchange/getPartTypes"):
            return json.dumps({"data": [{"id": "02269", "name": "Engine Oil Filter"}]})
        if url.endswith("/interchange/getManufacturers"):
            return json.dumps({"data": [{"id": "Mann + Hummel", "name": "Mann + Hummel"}]})
        if url.endswith("/search/cross-reference"):
            return card()
        return None


async def test_store_brand_is_discovered_as_candidate_not_exact_amazon_identity():
    result = await discover_interchanges(Reader(), {"brand": "MANN-FILTER", "identifiers": ["HU7025Z"]})
    assert result["status"] == "conditional" and result["product_relation"] == "interchange_candidate"
    assert result["replacement_candidates"][0]["part_number"] == "MGL57059"
    assert result["replacement_candidates"][0]["reference_part_number"] == "HU7025Z"
    assert result["lookup_stages"] == ["part_types", "manufacturer_candidates", "replacement_candidates"]


def test_wrong_reference_cannot_establish_cross_brand_link():
    parser = InterchangeHTML("HU7025Z", ["Mann + Hummel"])
    parser.feed(card(reference="HU6008Z"))
    assert parser.rows == []


async def test_successful_manufacturer_choices_do_not_prove_replacement_sku():
    class Blocked(Reader):
        async def read(self, url, **kwargs):
            if url.endswith("/search/cross-reference"):
                return "<html>Powered and protected by</html>"
            return await super().read(url, **kwargs)

    result = await discover_interchanges(Blocked(), {"brand": "MANN-FILTER", "identifiers": ["HU7025Z"]})
    assert result["status"] == "unavailable" and result["replacement_candidates"] == []
    assert result["lookup_stages"] == ["part_types", "manufacturer_candidates"]


@pytest.mark.parametrize("alternative_status", ["incompatible", "conditional", "unavailable", "matched"])
def test_other_brand_outcome_does_not_refute_requested_part(alternative_status):
    direct = PartsEvidence(
        source="autozone",
        status="matched",
        scope="vehicle_fitment",
        source_url="https://www.autozone.com",
        brand="MANN-FILTER",
        part_number="HU7025Z",
    )
    alternative = PartsEvidence(
        source="oreilly",
        status=alternative_status,
        scope="vehicle_fitment",
        source_url="https://www.oreillyauto.com",
        brand="MicroGard",
        part_number="MGL57059",
        product_relation="interchange_candidate",
    )
    result = retailer_cross_check([direct, alternative])
    assert result.status == "supported" and result.verified_sources == ["autozone"]


async def test_unverified_substitute_does_not_downgrade_confirmed_requested_part(monkeypatch):
    import httpx

    from tests.support.vin import VIN

    async def autozone(self, *args):
        return {
            "source": "autozone",
            "status": "matched",
            "scope": "vehicle_fitment",
            "source_url": "https://www.autozone.com",
        }

    async def oreilly(self, *args):
        return {
            "source": "oreilly",
            "status": "conditional",
            "scope": "catalog_application",
            "source_url": "https://www.oreillyauto.com",
            "product_relation": "interchange_candidate",
        }

    monkeypatch.setattr(AutoZoneParts, "assess", autozone)
    monkeypatch.setattr(OReillyParts, "assess", oreilly)

    def handle(request):
        return httpx.Response(
            200, text=amazon_html() if request.url.host == "www.amazon.com" else catalog_html()
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await PartsProvider(client, retailers_enabled=True).resolve(
            PartsRequest(amazon_url=URL, vin={"vin": VIN}), Decoder(), None
        )
    assert result.status == "compatible" and result.cross_check.status == "supported"


async def test_comparison_identity_batches_never_guess_store_line_codes():
    from gaswise.providers.parts.interchange import verify_candidate_identities

    candidates = [{"line_code": "MGD", "part_number": f"MGL{i}"} for i in range(5)]

    class Comparison:
        def __init__(self):
            self.batches = []

        async def read(self, url, **kwargs):
            items = kwargs["params"]["compares"].split(",")
            self.batches.append(items)
            assert len(items) <= 4
            return json.dumps(
                [
                    {
                        "lineCode": item.split("-")[0],
                        "itemNumber": item.split("-")[1],
                        "productName": "MicroGard Oil Filter",
                    }
                    for item in items
                ]
            )

    reader = Comparison()
    rows = await verify_candidate_identities(reader, candidates)
    assert [len(b) for b in reader.batches] == [4, 1]
    assert all(r["identity_status"] == "verified" for r in rows)


async def test_unrelated_comparison_metadata_does_not_verify_candidate():
    from gaswise.providers.parts.interchange import verify_candidate_identities

    class Wrong:
        async def read(self, *args, **kwargs):
            return json.dumps([{"lineCode": "WIX", "itemNumber": "57060", "productName": "WIX Oil Filter"}])

    result = await verify_candidate_identities(Wrong(), [{"line_code": "MGD", "part_number": "MGL57059"}])
    assert result[0]["identity_status"] == "unverified"


async def test_observed_model_identifier_is_tried_when_mpn_is_unrecognized():
    class ModelReader(Reader):
        async def read(self, url, **kwargs):
            if url.endswith("/interchange/getPartTypes") and kwargs["params"]["partNumber"] == "F00E160065":
                return json.dumps({"data": []})
            if url.endswith("/search/cross-reference"):
                return card(reference="3330")
            return await super().read(url, **kwargs)

    result = await discover_interchanges(
        ModelReader(), {"brand": "Bosch", "identifiers": ["F00E160065", "3330"]}
    )
    assert result["referenced_part_number"] == "3330" and result["replacement_candidates"]
    assert result["status"] == "conditional"


async def test_retailer_failure_preserves_other_source_and_blocks_unverified_use(monkeypatch):
    import httpx

    from tests.support.vin import VIN

    calls = []

    async def autozone(self, *args):
        calls.append("autozone")
        return {
            "source": "autozone",
            "status": "matched",
            "scope": "vehicle_fitment",
            "source_url": "https://www.autozone.com",
        }

    async def oreilly(self, *args):
        calls.append("oreilly")
        raise RuntimeError("private upstream detail must not escape")

    monkeypatch.setattr(AutoZoneParts, "assess", autozone)
    monkeypatch.setattr(OReillyParts, "assess", oreilly)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=amazon_html() if request.url.host == "www.amazon.com" else catalog_html()
            )
        )
    ) as client:
        result = await PartsProvider(client, retailers_enabled=True).resolve(
            PartsRequest(amazon_url=URL, vin={"vin": VIN}), Decoder(), None
        )
    assert set(calls) == {"autozone", "oreilly"}
    assert result.cross_check.source_statuses == {"autozone": "matched", "oreilly": "unavailable"}
    assert result.fitment_confirmed and result.usage_decision == "verified_fit"
    assert "private upstream detail" not in result.model_dump_json()
    for status, expected in [
        ("incompatible", "do_not_use"),
        ("needs_confirmation", "verification_required"),
        ("conflict", "verification_required"),
    ]:
        result.status = status
        assert result.usage_decision == expected and not result.fitment_confirmed
        assert result.model_dump()["usage_decision"] == expected
