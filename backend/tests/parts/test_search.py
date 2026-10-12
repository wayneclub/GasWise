from datetime import UTC, datetime
import json

import pytest

from gaswise.contracts.parts import PartsSearchRequest
from gaswise.contracts.vehicles import VinDecoded
from gaswise.services.parts.search import search_parts

VIN = "1HGCM82633A004352"
ATTRS = {"year": "2003", "makeId": "59", "modelId": "150", "vehicleTypeId": "1", "engineIds": {"engineBaseId": "123"}}
ROW = {"itemId": "111", "brandName": "TestBrand", "partNumber": "TEST123", "partGroupId": "azpg123", "productDetailsPageUrl": "/p/test-brand-filter/111", "productName": "TestBrand filter"}


class Decoder:
    async def decode(self, identity):
        return VinDecoded(vin_masked="*************4352", fetched_at=datetime.now(UTC), check_digit_matches=True, error_codes=["0"], year=2003, make="Honda", model="Accord")


class Parts:
    retailers_enabled = True
    calls = []
    response_fit = "FITS"
    returned_id = "111"
    restrictions = []
    blocked = False

    async def vehicle_identity(self, query, decoder, plate_provider):
        return query.vin, await decoder.decode(query.vin), ATTRS, []

    async def read(self, url, *, params=None, headers=None):
        self.calls.append((url, params))
        if self.blocked:
            return None
        if url.endswith("search-product"):
            return json.dumps({"searchResults": {"skuRecord": {"taxonomyPath": "/filters/oil-filter", "partGroupId": "azpg123"}}})
        if url.endswith("product-shelves"):
            assert params["year"] == "2003"
            assert params["vehicleQuestions"] == "engineBaseId:123"
            return json.dumps({"productShelfResults": {"skuRecords": [ROW]}})
        if url.endswith("/products"):
            return json.dumps({"pdpResults": {"products": [{"itemId": self.returned_id, "brandName": "TestBrand", "partNumber": "TEST123", "vehicleFitment": "VEHICLE_SPECIFIC", "vehicleFit": self.response_fit, "displayNotes": self.restrictions}]}})
        raise AssertionError(url)


@pytest.mark.parametrize("fit,expected", [("FITS", "compatible"), ("DOES_NOT_FIT", "incompatible"), ("UNKNOWN", "needs_confirmation")])
async def test_catalogue_discovery_requires_exact_native_vehicle_verdict(fit, expected):
    parts = Parts()
    parts.calls = []
    parts.response_fit = fit
    result = await search_parts(PartsSearchRequest(keyword="oil filter", vin={"vin": VIN}), parts, Decoder(), None)
    assert result.source_status == "ok"
    assert result.items[0].status == expected
    assert result.items[0].part_number == "TEST123"
    assert len(parts.calls) == 3


async def test_restrictions_and_wrong_sku_suppress_verified_fit():
    parts = Parts()
    parts.restrictions = ["Additional engine confirmation"]
    query = PartsSearchRequest(keyword="oil filter", vin={"vin": VIN})
    assert (await search_parts(query, parts, Decoder(), None)).items[0].status == "needs_confirmation"
    parts.restrictions = []
    parts.returned_id = "999"
    assert (await search_parts(query, parts, Decoder(), None)).items[0].status == "needs_confirmation"


async def test_blocked_catalogue_does_not_fabricate_results():
    parts = Parts()
    parts.blocked = True
    result = await search_parts(PartsSearchRequest(keyword="oil filter", vin={"vin": VIN}), parts, Decoder(), None)
    assert not result.items
    assert result.source_status == "unavailable"


def test_search_requires_identity_and_bounded_candidate_count():
    with pytest.raises(ValueError):
        PartsSearchRequest(keyword="oil filter")
    with pytest.raises(ValueError):
        PartsSearchRequest(keyword="oil filter", vin={"vin": VIN}, max_results=7)
