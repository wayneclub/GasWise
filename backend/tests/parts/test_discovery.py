import json

from gaswise.providers.parts.autozone import AutoZoneParts
from gaswise.providers.parts.discovery import category_pages, search_terms
from gaswise.providers.parts.oreilly import OReillyParts
from tests.support.parts import decoded

PRODUCT = {
    "brand": "Bosch",
    "identifiers": ["6091C"],
    "title": "Bosch 6091C HEPA Cabin Air Filter",
    "category": "Cabin Air Filter",
}


def test_search_uses_observed_identity_title_and_category_once():
    assert search_terms(PRODUCT) == ["6091C", "Bosch 6091C", PRODUCT["title"], "Cabin Air Filter"]
    assert len(search_terms({**PRODUCT, "identifiers": ["1", "2", "3"], "title": "x" * 1000})) <= 5
    assert all(len(t) <= 240 for t in search_terms({**PRODUCT, "title": "x" * 1000}))


async def test_category_fallback_finds_exact_part_then_explicit_make_rejection():
    calls = []

    class Reader:
        async def read(self, url, **kwargs):
            calls.append(url)
            if url.endswith("/search"):
                return "<h1>No results</h1>"
            if url.endswith("/shop/b"):
                return '<a href="/shop/b/filters/observed">Filters</a><a href="https://evil.test/shop/b/cabin">Cabin Air Filter</a>'
            if url.endswith("/shop/b/filters/observed"):
                return '<a href="/shop/b/filters/cabin/observed">Cabin Air Filters</a>'
            if url.endswith("/shop/b/filters/cabin/observed"):
                return '<a href="/detail/c/bosch/cabin-filter/bos0/6091c?q=tracking">Bosch 6091C</a><a href="/detail/c/bosch/cabin-filter/bos0/6091">similar</a>'
            if "/detail/c/" in url:
                return "<h1>Bosch Cabin Air Filter 6091C</h1>Part #: 6091C Line: BOS"
            if url.endswith("/product/compatible-makes"):
                return json.dumps({"compatibleMakes": ["CHEVROLET", "GMC"]})
            raise AssertionError(url)

    result = await OReillyParts(Reader()).assess(PRODUCT, decoded())
    assert result["status"] == "incompatible"
    assert "category_fallback" in result["lookup_stages"]
    assert all("evil.test" not in u for u in calls)
    assert all("6091?" not in u for u in calls)


async def test_ambiguous_category_branch_does_not_choose_arbitrary_product():
    class Reader:
        async def read(self, url, **kwargs):
            assert url.endswith("/shop/b")
            return '<a href="/shop/b/a">Cabin Air Filter</a><a href="/shop/b/b">Cabin Air Filters</a>'

    assert len(await category_pages(Reader(), PRODUCT)) == 1


async def test_autozone_title_fallback_still_requires_exact_brand_and_number():
    queries = []

    class Reader:
        async def read(self, url, **kwargs):
            params = kwargs["params"]
            if url.endswith("/search-product"):
                queries.append(params["searchedKeyword"])
                if params["searchedKeyword"] == PRODUCT["title"]:
                    return json.dumps(
                        {
                            "searchResults": {
                                "skuRecord": {"taxonomyPath": "/filters/cabin", "partGroupId": "azpg1"}
                            }
                        }
                    )
                return "{}"
            if url.endswith("/product-shelves"):
                return json.dumps(
                    {
                        "productShelfResults": {
                            "skuRecords": [
                                {
                                    "brandName": "Other",
                                    "partNumber": "6091C",
                                    "itemId": "10",
                                    "partGroupId": "azpg1",
                                },
                                {
                                    "brandName": "Bosch",
                                    "partNumber": "6091",
                                    "itemId": "11",
                                    "partGroupId": "azpg1",
                                },
                                {
                                    "brandName": "Bosch",
                                    "partNumber": "6091C",
                                    "itemId": "12",
                                    "partGroupId": "azpg1",
                                },
                            ]
                        }
                    }
                )
            raise AssertionError(url)

    class Provider(AutoZoneParts):
        async def native_fit(self, product, vehicle, row, *args):
            assert row["itemId"] == "12"
            return {"source": "autozone", "status": "incompatible", "scope": "vehicle_fitment"}

    result = await Provider(Reader()).assess(PRODUCT, decoded())
    assert result["status"] == "incompatible" and PRODUCT["title"] in queries


async def test_explicit_oem_reference_is_distinct_from_fuzzy_alternative():
    from gaswise.contracts.parts import PartsEvidence
    from gaswise.services.parts.fitment import retailer_cross_check

    rows = [
        {
            "brandName": "Store Brand",
            "partNumber": "ALT1",
            "itemId": "1",
            "partGroupId": "azpg1",
            "oemPartNumber": "6091C",
        },
        {
            "brandName": "Store Brand",
            "partNumber": "ALT2",
            "itemId": "2",
            "partGroupId": "azpg1",
            "oemPartNumber": "6091C",
        },
        {"brandName": "Unrelated", "partNumber": "OTHER", "itemId": "3", "partGroupId": "azpg1"},
    ]

    class Reader:
        manufacturers = [{"id": "Bosch", "name": "Bosch"}]

        async def read(self, url, **kwargs):
            if url.endswith("getPartTypes"):
                return json.dumps({"data": [{"id": "02700", "name": "Cabin Air Filter"}]})
            if url.endswith("getManufacturers"):
                return json.dumps({"data": self.manufacturers})
            if url.endswith("/search-product"):
                return json.dumps(
                    {
                        "searchResults": {
                            "skuRecord": {"taxonomyPath": "/filters/cabin-air-filter", "partGroupId": "azpg1"}
                        }
                    }
                )
            return json.dumps({"productShelfResults": {"skuRecords": rows}})

    class Provider(AutoZoneParts):
        def __init__(self, statuses):
            super().__init__(Reader())
            self.statuses, self.checked = statuses, []

        async def native_fit(self, product, vehicle, row, *args):
            self.checked.append(row["itemId"])
            return {"status": self.statuses[int(row["itemId"]) - 1], "scope": "vehicle_fitment"}

    for statuses, expected in [
        (["incompatible", "incompatible"], "rejected"),
        (["matched", "matched"], "supported"),
        (["matched", "incompatible"], "insufficient"),
        (["incompatible", "unavailable"], "insufficient"),
    ]:
        provider = Provider(statuses)
        result = await provider.assess(PRODUCT, decoded())
        assert provider.checked == ["1", "2"]
        cross = retailer_cross_check([PartsEvidence.model_validate(result)])
        assert cross.status == expected
        assert all(c["reference_field"] == "oemPartNumber" for c in result["replacement_candidates"])
    Reader.manufacturers = [{"name": "Bosch"}, {"name": "Other"}]
    provider = Provider(["incompatible", "incompatible"])
    result = await provider.assess(PRODUCT, decoded())
    assert result["product_relation"] == "interchange_candidate" and result["status"] == "conditional"
    rows[0]["oemPartNumber"] = "similar6091"
    rows[1]["oemPartNumber"] = "similar6091"
    provider = Provider(["incompatible", "incompatible"])
    result = await provider.assess(PRODUCT, decoded())
    assert not provider.checked and result["status"] == "no_match"
