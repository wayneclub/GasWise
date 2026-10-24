"""Bounded retailer discovery followed by exact-SKU native vehicle checks."""
import asyncio
import re

from gaswise.contracts.parts import PartCandidate, PartsEvidence, PartsSearchResult
from gaswise.providers.parts.autozone import BASE, HEADERS, ROOT, AutoZoneParts, load
from gaswise.providers.vehicles.plate import AutoZonePlateProvider


async def search_parts(query, parts, decoder, plate_provider):
    identity, vehicle, attrs, warnings = await parts.vehicle_identity(query, decoder, plate_provider)
    result = PartsSearchResult(keyword=query.keyword, vehicle=vehicle, items=[], source_status="unavailable", warnings=warnings)
    result.warnings.append("Bounded retailer search; catalogue absence does not prove incompatibility. Each candidate requires its own exact-SKU vehicle check.")
    if not parts.retailers_enabled:
        result.source_status = "not_configured"
        return result
    if not vehicle.check_digit_matches or set(vehicle.error_codes) != {"0"}:
        result.warnings.append("Decoded vehicle identity is incomplete; no verified-fit claim was made.")
        return result
    if attrs is None:
        data = load(await parts.read(AutoZonePlateProvider.url, params={"vin": identity.vin, "callingClient": "DIY-DESKTOP", "country": "USA"}, headers=AutoZonePlateProvider.headers))
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) and data[0].get("vin") == identity.vin:
            attrs = data[0].get("acesVehicleAttributes")
    scoped = {}
    if isinstance(attrs, dict) and str(attrs.get("year")) == str(vehicle.year):
        required = ("year", "makeId", "modelId", "vehicleTypeId")
        if all(str(attrs.get(k, "")).isdigit() for k in required):
            scoped.update({k: attrs[k] for k in required})
            engines = attrs.get("engineIds")
            values = {**attrs, **(engines if isinstance(engines, dict) else {})}
            excluded = {"acesVehicleId", "partsProVehicleId", "vehicleTypeId", "catalogVehicleId", "vehicleId", "makeId", "modelId"}
            scoped["vehicleQuestions"] = "||".join(f"{k}:{v}" for k, v in values.items() if ("Id" in k or "ID" in k) and k not in excluded and isinstance(v, (str, int)) and re.fullmatch(r"[0-9_]+", str(v)))
    search_url = ROOT + "/sls/pd/product-browse-search/v1/search-product"
    nav = load(await parts.read(search_url, params={**BASE, "searchedKeyword": query.keyword, **scoped}, headers=HEADERS))
    try:
        record = nav["searchResults"]["skuRecord"]
        path, group = record["taxonomyPath"], record["partGroupId"]
        if not isinstance(path, str) or not re.fullmatch(r"/[a-zA-Z0-9/-]+", path) or not re.fullmatch(r"(?:azpg)?\d+", group):
            return result
    except (KeyError, TypeError):
        if nav is not None:
            result.source_status = "no_match"
        return result
    shelf_url = ROOT + "/sls/b2c/product-discovery-browse-search-data/v2/product-shelves"
    data = load(await parts.read(shelf_url, params={**BASE, "searchedKeyword": query.keyword, "canonicalPath": path, "partGroupId": group, "pageNumber": 1, "recordsPerPage": 12, **scoped}, headers=HEADERS))
    try:
        rows = data["productShelfResults"]["skuRecords"]
        if not isinstance(rows, list):
            return result
    except (KeyError, TypeError):
        return result
    result.source_status = "ok" if rows else "no_match"
    seen, candidates = set(), []
    checker = AutoZoneParts(parts)
    for row in rows[:12]:
        if len(candidates) >= query.max_results:
            break
        if not isinstance(row, dict) or not str(row.get("itemId", "")).isdigit() or row.get("partGroupId") != group:
            continue
        item_id = str(row["itemId"])
        brand, number, product_path = row.get("brandName"), row.get("partNumber"), row.get("productDetailsPageUrl")
        if item_id in seen or not all(isinstance(v, str) and v for v in (brand, number, product_path)) or not re.fullmatch(r"/p/[a-zA-Z0-9/-]+", product_path):
            continue
        seen.add(item_id)
        candidates.append(row)
    slots = asyncio.Semaphore(2)

    async def check_candidate(row):
        brand, number, product_path = row["brandName"], row["partNumber"], row["productDetailsPageUrl"]
        product = {"brand": brand, "identifiers": [number]}
        async with slots:
            proof = await checker.native_fit(product, vehicle, row, attrs, None)
        if proof is None:
            proof = {"source": "autozone", "status": "conditional", "scope": "vehicle_fitment", "source_url": "https://www.autozone.com" + product_path, "detail": "Exact supplier vehicle configuration is unavailable; product discovery is not vehicle-fit proof."}
        evidence = PartsEvidence.model_validate(proof)
        status = "compatible" if evidence.status == "matched" and evidence.scope == "vehicle_fitment" else "incompatible" if evidence.status == "incompatible" else "needs_confirmation"
        return PartCandidate(name=row.get("productName") or row.get("displayName") or f"{brand} {number}", brand=brand, part_number=number, product_url="https://www.autozone.com" + product_path, status=status, evidence=evidence)

    result.items = await asyncio.gather(*(check_candidate(row) for row in candidates))
    result.candidate_count = len(rows)
    result.items.sort(key=lambda item: {"compatible": 0, "needs_confirmation": 1, "incompatible": 2}[item.status])
    return result
