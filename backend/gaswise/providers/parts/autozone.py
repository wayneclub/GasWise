"""Dynamic public SKU discovery and supplier application hierarchy."""

import json
import re

from gaswise.providers.parts.discovery import search_terms, words
from gaswise.providers.parts.product import brand_key, compact

ROOT = "https://external-api.autozone.com"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.autozone.com/",
    "X-Requested-By": "MF",
    "sales-channel": "AZRMFWEB",
}
BASE = {"country": "USA", "customerType": "B2C", "salesChannel": "ECOMM", "preview": "false"}
FIT = ROOT + "/sls/pd/product-lookup/v1/product-vehicle-fitments"


def load(raw):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def evidence(status, url, **extra):
    return {
        "source": "autozone",
        "status": status,
        "scope": "catalog_application",
        "source_url": url,
        **extra,
    }


class AutoZoneParts:
    def __init__(self, reader):
        self.reader = reader

    async def assess(self, product, vehicle, vehicle_context=None, identity=None):
        search = ROOT + "/sls/pd/product-browse-search/v1/search-product"
        candidates = []
        references = {}
        stages = []
        for number in search_terms(product):
            stages.append(
                "exact_identifier_search" if number in product["identifiers"] else "title_or_category_search"
            )
            nav = load(
                await self.reader.read(search, params={**BASE, "searchedKeyword": number}, headers=HEADERS)
            )
            try:
                record = nav["searchResults"]["skuRecord"]
                path, group = record["taxonomyPath"], record["partGroupId"]
                if (
                    not isinstance(path, str)
                    or not path.startswith("/")
                    or not re.fullmatch(r"azpg\d+", group)
                ):
                    continue
            except (KeyError, TypeError):
                continue
            shelves = ROOT + "/sls/b2c/product-discovery-browse-search-data/v2/product-shelves"
            data = load(
                await self.reader.read(
                    shelves,
                    params={
                        **BASE,
                        "searchedKeyword": number,
                        "canonicalPath": path,
                        "partGroupId": group,
                        "pageNumber": 1,
                        "recordsPerPage": 24,
                    },
                    headers=HEADERS,
                )
            )
            try:
                rows = data["productShelfResults"]["skuRecords"]
                if not isinstance(rows, list):
                    continue
                for row in rows[:24]:
                    if (
                        isinstance(row, dict)
                        and compact(row.get("oemPartNumber")) in {compact(n) for n in product["identifiers"]}
                        and str(row.get("itemId", "")).isdigit()
                        and row.get("partGroupId") == group
                        and row.get("brandName")
                        and row.get("partNumber")
                        and words(path.rsplit("/", 1)[-1])
                        <= words(product.get("category") or product.get("title"))
                    ):
                        references[str(row["itemId"])] = row
                    if (
                        isinstance(row, dict)
                        and brand_key(row.get("brandName")) == brand_key(product["brand"])
                        and compact(row.get("partNumber")) in {compact(n) for n in product["identifiers"]}
                        and isinstance(row.get("itemId"), (str, int))
                        and str(row["itemId"]).isdigit()
                        and row.get("partGroupId") == group
                    ):
                        candidates.append(row)
            except (KeyError, TypeError):
                continue
            if candidates:
                break
        unique = {str(r["itemId"]): r for r in candidates}
        if not unique and references:
            return await self.assess_references(product, vehicle, references, vehicle_context, identity)
        if len(unique) != 1:
            return evidence(
                "ambiguous" if unique else "no_match",
                search,
                detail="No unique exact brand/observed part-number SKU; fuzzy search hits are excluded.",
                lookup_stages=list(dict.fromkeys(stages)),
            )
        row = next(iter(unique.values()))
        native = await self.native_fit(product, vehicle, row, vehicle_context, identity)
        if native is not None:
            return native
        params = {**BASE, "itemId": row["itemId"], "partGroupId": row["partGroupId"]}
        makes = load(await self.reader.read(FIT, params=params, headers=HEADERS))
        if not isinstance(makes, list) or not makes or len(makes) > 500:
            return evidence(
                "unavailable", FIT, detail="Supplier application makes unavailable or incomplete."
            )
        target = [r for r in makes if isinstance(r, dict) and compact(r.get("name")) == compact(vehicle.make)]
        proof = {
            "brand": row["brandName"],
            "part_number": row["partNumber"],
            "catalog_product_id": str(row["itemId"]),
        }
        if not target:
            return evidence(
                "incompatible",
                FIT,
                **proof,
                detail="Exact part supplier application list does not include this vehicle make.",
            )
        if len(target) != 1 or not isinstance(target[0].get("id"), int):
            return evidence("ambiguous", FIT, **proof)
        params["makeId"] = target[0]["id"]
        models = load(await self.reader.read(FIT, params=params, headers=HEADERS))
        if not isinstance(models, list) or len(models) > 1000:
            return evidence("unavailable", FIT, **proof)
        names = {compact(v) for v in (vehicle.model, vehicle.trim) if v}
        target = [r for r in models if isinstance(r, dict) and compact(r.get("name")) in names]
        if not target:
            return evidence(
                "incompatible" if models else "unavailable",
                FIT,
                **proof,
                detail="No matching model in the exact part application list.",
            )
        if len(target) != 1 or not isinstance(target[0].get("id"), int):
            return evidence("ambiguous", FIT, **proof)
        params["modelId"] = target[0]["id"]
        years = load(await self.reader.read(FIT, params=params, headers=HEADERS))
        if not isinstance(years, list) or not years or len(years) > 150:
            return evidence("unavailable", FIT, **proof)
        matched = [r for r in years if isinstance(r, dict) and str(r.get("name")) == str(vehicle.year)]
        if len(matched) != 1:
            return evidence(
                "incompatible" if not matched else "ambiguous",
                FIT,
                **proof,
                detail="Vehicle year is absent or ambiguous in the supplier part applications.",
            )
        return evidence(
            "matched",
            FIT,
            **proof,
            matched_fields=["year", "make", "model"],
            detail="Exact brand/part SKU lists this year/make/model; engine/production options are not verified by this hierarchy.",
        )

    async def native_fit(self, product, vehicle, row, attrs, identity):
        from gaswise.providers.vehicles.plate import AutoZonePlateProvider

        headers = AutoZonePlateProvider.headers
        if attrs is None and identity is not None:
            data = load(
                await self.reader.read(
                    AutoZonePlateProvider.url,
                    params={"vin": identity.vin, "callingClient": "DIY-DESKTOP", "country": "USA"},
                    headers=headers,
                )
            )
            if (
                isinstance(data, list)
                and len(data) == 1
                and isinstance(data[0], dict)
                and data[0].get("vin") == identity.vin
            ):
                attrs = data[0].get("acesVehicleAttributes")
        if not isinstance(attrs, dict) or str(attrs.get("year")) != str(vehicle.year):
            return None
        required = ("makeId", "modelId", "vehicleTypeId")
        if not all(str(attrs.get(k, "")).isdigit() for k in required):
            return None
        values = dict(attrs)
        engines = values.pop("engineIds", {})
        if not isinstance(engines, dict) or not engines.get("engineBaseId"):
            return None
        values.update(engines)
        excluded = {
            "acesVehicleId",
            "partsProVehicleId",
            "vehicleTypeId",
            "catalogVehicleId",
            "vehicleId",
            "makeId",
            "modelId",
        }
        questions = "||".join(
            f"{k}:{v}"
            for k, v in values.items()
            if ("Id" in k or "ID" in k)
            and k not in excluded
            and isinstance(v, (str, int))
            and re.fullmatch(r"[0-9_]+", str(v))
        )
        path = row.get("productDetailsPageUrl")
        if not isinstance(path, str) or not re.fullmatch(r"/p/[a-zA-Z0-9/-]+", path):
            return None
        url = ROOT + "/sls/b2c/product-discovery-product-data/v2/products"
        data = load(
            await self.reader.read(
                url,
                params={
                    "country": "USA",
                    "preview": "false",
                    "productDetailsPageUrl": path,
                    "partGroupId": row["partGroupId"],
                    "year": attrs["year"],
                    **{k: attrs[k] for k in required},
                    "vehicleQuestions": questions,
                },
                headers=headers,
            )
        )
        try:
            items = data["pdpResults"]["products"]
            matches = [
                p
                for p in items
                if isinstance(p, dict)
                and str(p.get("itemId")) == str(row["itemId"])
                and brand_key(p.get("brandName")) == brand_key(product["brand"])
                and compact(p.get("partNumber")) in {compact(n) for n in product["identifiers"]}
            ]
        except (KeyError, TypeError):
            return evidence(
                "unavailable", url, scope="vehicle_fitment", detail="Native fitment response unavailable."
            )
        if len(matches) != 1:
            return evidence(
                "ambiguous",
                url,
                scope="vehicle_fitment",
                detail="Native response does not identify one exact SKU.",
            )
        item = matches[0]
        proof = {
            "brand": item["brandName"],
            "part_number": item["partNumber"],
            "catalog_product_id": str(item["itemId"]),
            "scope": "vehicle_fitment",
        }
        if item.get("vehicleFitment") != "VEHICLE_SPECIFIC":
            return evidence(
                "conditional", url, **proof, detail="Vehicle-specific fitment is not established."
            )
        if any(
            item.get(k)
            for k in ("displayNotes", "displayNotesTypes", "applicationQuestions", "fitmentQuestions")
        ):
            return evidence(
                "conditional",
                url,
                **proof,
                detail="Supplier returned application restrictions or additional questions.",
            )
        status = {"FITS": "matched", "DOES_NOT_FIT": "incompatible"}.get(
            item.get("vehicleFit"), "unavailable"
        )
        return evidence(
            status,
            url,
            **proof,
            matched_fields=["year", "make", "model", "supplier_vehicle_configuration"],
            detail="AutoZone native exact-SKU check using the complete VIN-derived vehicle configuration: "
            + str(item.get("vehicleFit")),
        )

    async def assess_references(self, product, vehicle, references, attrs, identity):
        """Only explicit OEM references can link retailer alternatives to the requested part."""
        reference_brand_verified = await self.reference_brand_verified(product, references)
        rows = list(references.values())[:3]
        candidates, results = [], []
        for row in rows:
            substitute = {"brand": row["brandName"], "identifiers": [row["partNumber"]]}
            result = await self.native_fit(substitute, vehicle, row, attrs, identity)
            result = result or {"status": "unavailable", "scope": "catalog_application"}
            results.append(result)
            candidates.append(
                {
                    "brand": row["brandName"],
                    "part_number": row["partNumber"],
                    "catalog_product_id": str(row["itemId"]),
                    "reference_part_number": row["oemPartNumber"],
                    "reference_field": "oemPartNumber",
                    "fitment_status": result["status"],
                }
            )
        decisions = {r["status"] for r in results}
        verified = (
            reference_brand_verified
            and len(references) <= 3
            and len(decisions) == 1
            and decisions <= {"matched", "incompatible"}
            and all(r["scope"] == "vehicle_fitment" for r in results)
        )
        return evidence(
            next(iter(decisions)) if verified else "conditional",
            ROOT + "/sls/b2c/product-discovery-browse-search-data/v2/product-shelves",
            scope="vehicle_fitment" if verified else "catalog_application",
            brand=product["brand"],
            part_number=product["identifiers"][0],
            product_relation="verified_interchange" if verified else "interchange_candidate",
            referenced_part_number=product["identifiers"][0],
            interchange_source_url="https://www.oreillyauto.com/interchange/getManufacturers",
            replacement_candidates=candidates,
            lookup_stages=[
                "explicit_oem_reference",
                "reference_manufacturer_verified"
                if reference_brand_verified
                else "reference_manufacturer_unresolved",
                "replacement_native_fitment",
            ],
            conditions=[]
            if verified
            else ["Referenced alternatives require consistent complete native fitment evidence."],
            detail="Explicit retailer OEM references and native checks of referenced alternatives; fuzzy search hits are excluded.",
        )

    async def reference_brand_verified(self, product, references):
        """Disambiguate a part-number-only OEM link with the other retailer's manufacturer index."""
        numbers = {compact(row["oemPartNumber"]) for row in references.values()}
        if len(numbers) != 1:
            return False
        number = next(iter(numbers))
        root = "https://www.oreillyauto.com/interchange/"
        data = load(
            await self.reader.read(
                root + "getPartTypes", params={"partNumber": number}, headers={"Accept": "application/json"}
            )
        )
        rows = data.get("data") if isinstance(data, dict) else None
        target = words(product.get("category") or product.get("title"))
        types = (
            [
                r
                for r in rows
                if isinstance(r, dict)
                and words(r.get("name"))
                and words(r.get("name")) <= target
                and str(r.get("id", "")).isdigit()
            ]
            if isinstance(rows, list)
            else []
        )
        if len(types) != 1:
            return False
        data = load(
            await self.reader.read(
                root + "getManufacturers",
                json_body={"q": number, "partNumber": number, "partTypeIds": [types[0]["id"]]},
                headers={"Accept": "application/json"},
            )
        )
        rows = data.get("data") if isinstance(data, dict) else None
        return (
            isinstance(rows, list)
            and len(rows) == 1
            and isinstance(rows[0], dict)
            and brand_key(rows[0].get("name")) == brand_key(product["brand"])
        )
