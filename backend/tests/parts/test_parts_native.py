import json

import pytest

from gaswise.providers.parts.autozone import AutoZoneParts
from gaswise.providers.parts.product import identify_amazon
from tests.support.parts import decoded
from tests.support.paths import REPO_ROOT

PRODUCT = dict(brand="Bosch", identifiers=["F00E160065", "3330"])
ROW = dict(
    itemId="123",
    brandName="Bosch",
    partNumber="3330",
    partGroupId="azpg1622",
    productDetailsPageUrl="/p/bosch-filter/123",
)
ATTRS = dict(
    year="2018",
    makeId="63",
    modelId="23483",
    vehicleTypeId="5",
    engineIds={"engineBaseId": "2073_749_520"},
    engineDesignationId="15405",
)


class Reader:
    def __init__(self, item):
        self.item = item
        self.params = None

    async def read(self, url, **kwargs):
        self.params = kwargs["params"]
        assert "vin" not in self.params and "licensePlate" not in self.params
        return json.dumps({"pdpResults": {"products": [self.item]}})


@pytest.mark.parametrize(
    "flag,status", [("FITS", "matched"), ("DOES_NOT_FIT", "incompatible"), ("UNKNOWN", "unavailable")]
)
async def test_native_configuration_not_manual_part_questions(flag, status):
    reader = Reader({**ROW, "vehicleFit": flag, "vehicleFitment": "VEHICLE_SPECIFIC"})
    result = await AutoZoneParts(reader).native_fit(PRODUCT, decoded(), ROW, ATTRS, None)
    assert result["status"] == status and result["scope"] == "vehicle_fitment"
    assert "engineBaseId:2073_749_520" in reader.params["vehicleQuestions"]
    assert "engineDesignationId:15405" in reader.params["vehicleQuestions"]
    assert "makeId:" not in reader.params["vehicleQuestions"]


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"itemId": "999"}, "ambiguous"),
        ({"brandName": "Unknown"}, "ambiguous"),
        ({"displayNotes": "Only before production date"}, "conditional"),
        ({"applicationQuestions": [{"required": True}]}, "conditional"),
        ({"vehicleFitment": "UNIVERSAL"}, "conditional"),
    ],
)
async def test_wrong_sku_or_restrictions_never_confirm(changes, status):
    reader = Reader({**ROW, "vehicleFit": "FITS", "vehicleFitment": "VEHICLE_SPECIFIC", **changes})
    assert (await AutoZoneParts(reader).native_fit(PRODUCT, decoded(), ROW, ATTRS, None))["status"] == status


async def test_missing_supplier_engine_configuration_not_native_proof():
    attrs = {**ATTRS, "engineIds": {}}
    assert await AutoZoneParts(Reader(None)).native_fit(PRODUCT, decoded(), ROW, attrs, None) is None


def test_generic_other_brand_preserves_mpn_and_model():

    root = REPO_ROOT / "artifacts" / "amazon-research"
    for asin, brand in [("B019IPTB0W", "Mann"), ("B002EBSLA4", "Bosch")]:
        result = identify_amazon(
            (root / f"{asin}-identity-minimal.html").read_text(), f"https://www.amazon.com/dp/{asin}"
        )
        assert result["status"] == "identified" and brand.lower() in result["brand"].lower()
        if asin == "B002EBSLA4":
            assert result["mpn"] == "F00E160065" and result["model_number"] == "3330"


@pytest.mark.parametrize(
    "statuses,scopes,expected,verified",
    [
        (
            ("matched", "matched"),
            ("vehicle_fitment", "vehicle_fitment"),
            "supported",
            ["autozone", "oreilly"],
        ),
        (
            ("incompatible", "incompatible"),
            ("vehicle_fitment", "vehicle_fitment"),
            "rejected",
            ["autozone", "oreilly"],
        ),
        (("matched", "unavailable"), ("vehicle_fitment", "catalog_application"), "supported", ["autozone"]),
        (("matched", "matched"), ("catalog_application", "catalog_application"), "insufficient", []),
        (
            ("matched", "incompatible"),
            ("vehicle_fitment", "vehicle_fitment"),
            "conflict",
            ["autozone", "oreilly"],
        ),
        (("matched", "conditional"), ("vehicle_fitment", "catalog_application"), "supported", ["autozone"]),
    ],
)
def test_two_retailer_cross_check_never_claims_blocked_source_verified(statuses, scopes, expected, verified):
    from gaswise.contracts.parts import PartsEvidence
    from gaswise.services.parts.fitment import retailer_cross_check

    evidence = [
        PartsEvidence(source=source, status=status, scope=scope, source_url="https://example.com")
        for source, status, scope in zip(("autozone", "oreilly"), statuses, scopes, strict=True)
    ]
    result = retailer_cross_check(evidence)
    assert result.status == expected and result.verified_sources == verified
    assert result.source_statuses == dict(zip(("autozone", "oreilly"), statuses, strict=True))
