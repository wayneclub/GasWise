"""Bounded public product identification and manufacturer application evidence."""

import asyncio
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote

from gaswise.contracts.parts import PartsCrossCheck as PartsCrossCheck
from gaswise.contracts.parts import PartsEvidence as PartsEvidence
from gaswise.contracts.parts import PartsRequest as PartsRequest
from gaswise.contracts.parts import PartsResult as PartsResult
from gaswise.domain.ports import ProviderError
from gaswise.domain.validation.urls import amazon_url as amazon_url
from gaswise.providers.http.httpx_public import HTTPXPublicReader
from gaswise.providers.parts.autozone import AutoZoneParts
from gaswise.providers.parts.mann import MannRows, match_mann_rows
from gaswise.providers.parts.oreilly import OReillyParts
from gaswise.providers.parts.product import brand_key, identify_amazon


def retailer_cross_check(evidence):
    retailers = [e for e in evidence if e.source in {"autozone", "oreilly"}]
    states = {"autozone": "not_queried", "oreilly": "not_queried"}
    states.update({e.source: e.status for e in retailers})
    direct = [e for e in retailers if e.product_relation in {"direct_product", "verified_interchange"}]
    decisions = {
        e.source: e.status
        for e in direct
        if e.scope == "vehicle_fitment" and e.status in {"matched", "incompatible"}
    }
    result = PartsCrossCheck(source_statuses=states, verified_sources=sorted(decisions))
    if any(e.status == "matched" for e in direct) and any(e.status == "incompatible" for e in direct):
        result.status = "conflict"
        result.detail = (
            "Sources disagree about the requested product's application, not about store-brand availability."
        )
    elif "matched" in decisions.values():
        result.status = "supported"
        result.detail = "The requested product has verified vehicle fitment; another retailer need not stock the same brand or part."
    elif "incompatible" in decisions.values():
        result.status = "rejected"
        result.detail = (
            "Exact-product or manufacturer-verified OEM-reference fitment rejects the requested application."
        )
    return result


class ApplicationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("data-g-binding-params", "")
        if tag == "a" and "vehicleName%3D" in value:
            row = {k: v[0] for k, v in parse_qs(unquote(value).lstrip("?"), keep_blank_values=True).items()}
            keys = (
                "vehicleMake",
                "vehicleName",
                "modelSeriesName",
                "engineCode",
                "ccm",
                "vehicleManufacturedFrom",
                "vehicleManufacturedTo",
                "serialNumberRange",
            )
            if all(row.get(k) for k in keys[:-1]):
                row = {k: row.get(k, "") for k in keys}
                if row not in self.rows:
                    self.rows.append(row)


def compact(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def assess_applications(vehicle, rows):
    """Absence from a regional catalog is not evidence of incompatibility."""
    names = [compact(v) for v in (vehicle.trim, vehicle.model, vehicle.series) if v]
    candidates = []
    for row in rows:
        name = compact(row["vehicleName"])
        if compact(row["vehicleMake"]) != compact(vehicle.make):
            continue
        if not any(name == n or name == n + "4MATIC" for n in names):
            continue
        try:
            first, last = int(row["vehicleManufacturedFrom"][:4]), int(row["vehicleManufacturedTo"][:4])
            liters = float(row["ccm"]) / 1000
        except (ValueError, TypeError):
            continue
        if vehicle.year is None or not first <= vehicle.year <= last:
            continue
        if vehicle.engine_liters is None or abs(float(vehicle.engine_liters) - liters) > 0.06:
            continue
        candidates.append(row)
    if not candidates:
        return (
            "needs_confirmation",
            [],
            ["No exact application candidate; regional catalog absence does not prove non-fitment."],
        )
    # Exact engine-code evidence is necessary; displacement alone is insufficient.
    confirmed = []
    for row in candidates:
        if not vehicle.model or compact(vehicle.model) not in compact(row["modelSeriesName"]):
            continue
        if not vehicle.series or compact(vehicle.series) not in compact(row["modelSeriesName"]):
            continue
        if not vehicle.engine_model or compact(vehicle.engine_model) != compact(row["engineCode"]):
            continue
        if "4MATIC" in compact(row["vehicleName"]) and not vehicle.drive:
            continue
        if "4MATIC" in compact(row["vehicleName"]) and not any(
            x in vehicle.drive.lower() for x in ("all-wheel", "4wd", "4-wheel", "awd")
        ):
            continue
        if row["serialNumberRange"] or vehicle.year in {
            int(row["vehicleManufacturedFrom"][:4]),
            int(row["vehicleManufacturedTo"][:4]),
        }:
            continue
        confirmed.append(row)
    if confirmed and set(vehicle.error_codes) == {"0"} and vehicle.check_digit_matches:
        return (
            "compatible",
            confirmed,
            [
                "Manufacturer application matches decoded identity and exact engine code; no serial restriction in the matched row."
            ],
        )
    return (
        "needs_confirmation",
        candidates,
        [
            "Application candidates found, but engine code, chassis series, drivetrain or production/serial restrictions need confirmation."
        ],
    )


class PartsProvider:
    def __init__(self, client, public_http=None, retailers_enabled=False):
        self.client = client
        self.public_http = public_http
        self.retailers_enabled = retailers_enabled

    async def read(self, url, **kwargs):
        if self.public_http is not None:
            return await self.public_http.read(url, **kwargs)
        return await self.public_html(url, **kwargs)

    async def public_html(self, url, params=None, headers=None, json_body=None, max_bytes=4_000_000):
        return await HTTPXPublicReader(self.client).read(
            url,
            params=params,
            headers=headers,
            json_body=json_body,
            max_bytes=max_bytes,
        )

    async def vehicle_identity(self, query, decoder, plate_provider):
        warnings = []
        identity = query.vin
        vehicle_context = None
        if query.plate:
            if plate_provider is None:
                raise ProviderError("plate_provider_not_configured")
            if hasattr(plate_provider, "vehicle_context"):
                identity, make, model, vehicle_context = await plate_provider.vehicle_context(query.plate)
            else:
                identity, make, model = await plate_provider.vin(query.plate)
            warnings.append("Confirm returned identity; plate records may lag transfers.")
        vehicle = await decoder.decode(identity)
        if query.plate and compact(make) != compact(vehicle.make):
            raise ProviderError("plate_vin_vehicle_mismatch")
        return identity, vehicle, vehicle_context, warnings

    async def resolve(self, query, decoder, plate_provider):
        identity, vehicle, vehicle_context, warnings = await self.vehicle_identity(query, decoder, plate_provider)
        product = identify_amazon(
            await self.read(query.amazon_url, headers={"Accept": "text/html"}), query.amazon_url
        )
        if query.brand and query.part_number:
            if product["status"] == "identified" and (
                brand_key(product["brand"]) != brand_key(query.brand)
                or compact(query.part_number) not in {compact(n) for n in product["identifiers"]}
            ):
                product["status"] = "conflict"
            elif product["status"] != "identified":
                product.update(
                    status="user_supplied_unverified",
                    brand=query.brand,
                    mpn=query.part_number,
                    identifiers=[query.part_number],
                )
        result = PartsResult(
            status="needs_confirmation",
            amazon_url=query.amazon_url,
            product_status=product["status"],
            title=product["title"],
            brand=product["brand"],
            part_number=product["mpn"],
            model_number=product["model_number"],
            category=product["category"],
            vehicle=vehicle,
            source_urls=[query.amazon_url],
            warnings=warnings,
        )
        result.evidence.append(
            PartsEvidence(
                source="amazon",
                scope="product_identity",
                source_url=query.amazon_url,
                status="matched"
                if product["status"] == "identified"
                else "ambiguous"
                if product["status"] == "conflict"
                else "unavailable",
                detail="Selected ASIN, labeled brand, manufacturer part number and model number are distinct identity fields.",
            )
        )
        if product["status"] == "conflict":
            result.status = "conflict"
            result.reasons.append("Supplied part identity conflicts with the selected Amazon ASIN.")
            return result
        if not product["identifiers"]:
            result.reasons.append("Selected product could not be identified; no fitment guess was made.")
            return result
        rows = []
        if brand_key(product["brand"]) == "MANN" and re.fullmatch(
            r"[A-Z]+[0-9]{2,6}[A-Z]?", compact(product["mpn"])
        ):
            number = compact(product["mpn"]).lower()
            url = (
                "https://www.mann-filter.com/us-en/catalog/search-results/product.html/"
                + number
                + "_mann-filter.html"
            )
            result.source_urls.append(url)
            html = await self.read(url, headers={"Accept": "text/html"})
            if html and compact(product["mpn"]) in compact(html):
                parsed = MannRows()
                parsed.feed(html)
                status, rows, conditions, reasons = match_mann_rows(vehicle, parsed.rows)
                # Retain old complete-engine global catalog matching when explicit US-year rows are absent.
                old = ApplicationParser()
                old.feed(html)
                old_status, old_rows, old_reasons = assess_applications(vehicle, old.rows)
                exact = old_status == "compatible"
                result.applications = rows or old_rows
                result.evidence.append(
                    PartsEvidence(
                        source="manufacturer",
                        status="matched" if exact else status,
                        scope="engine_application" if exact else "catalog_application",
                        source_url=url,
                        conditions=conditions,
                        matched_fields=["year", "make", "model", "engine_liters"],
                        detail="; ".join(old_reasons if exact else reasons),
                    )
                )
            else:
                result.evidence.append(
                    PartsEvidence(
                        source="manufacturer",
                        status="unavailable",
                        scope="catalog_application",
                        source_url=url,
                    )
                )
        supplier_tasks = []
        if self.retailers_enabled:
            supplier_tasks = [
                AutoZoneParts(self).assess(product, vehicle, vehicle_context, identity),
                OReillyParts(self).assess(product, vehicle, query.oreilly_product_url, identity),
            ]
        if supplier_tasks:
            outcomes = await asyncio.gather(*supplier_tasks, return_exceptions=True)
            supplier_results = []
            for source, outcome in zip(("autozone", "oreilly"), outcomes, strict=True):
                if isinstance(outcome, Exception):
                    outcome = {
                        "source": source,
                        "status": "unavailable",
                        "scope": "catalog_application",
                        "source_url": (
                            "https://www.autozone.com"
                            if source == "autozone"
                            else "https://www.oreillyauto.com"
                        ),
                        "provider_error": "provider_lookup_failed",
                        "detail": "Retailer lookup failed; the other retailer is assessed independently.",
                    }
                elif isinstance(outcome, BaseException):
                    raise outcome
                supplier_results.append(outcome)
            result.evidence.extend(PartsEvidence.model_validate(e) for e in supplier_results)
            result.source_urls = list(
                dict.fromkeys([*result.source_urls, *[e["source_url"] for e in supplier_results]])
            )
        result.cross_check = retailer_cross_check(result.evidence)
        fit = [
            e
            for e in result.evidence
            if e.scope != "product_identity"
            and e.product_relation in {"direct_product", "verified_interchange"}
        ]
        positives = [e for e in fit if e.status == "matched"]
        negatives = [e for e in fit if e.status == "incompatible"]
        if positives and negatives:
            result.status = "conflict"
            result.reasons.append("Catalog sources disagree; automatic compatibility is suppressed.")
        elif negatives:
            result.status = "incompatible"
            result.verification_scope = next(
                (e.scope for e in negatives if e.scope == "vehicle_fitment"), "catalog_application"
            )
            result.reasons.extend(e.detail or "Supplier rejects this application." for e in negatives)
        elif any(e.status == "conditional" for e in fit):
            result.reasons.extend(c for e in fit for c in e.conditions)
        elif positives:
            strong = next(
                (e for e in positives if e.scope in {"engine_application", "vehicle_fitment"}), None
            )
            if strong:
                result.status = "compatible"
                result.verification_scope = strong.scope
                result.reasons.append(
                    strong.detail or "Supplier vehicle configuration and exact product match."
                )
            else:
                result.verification_scope = "catalog_application"
                result.reasons.append(
                    "Catalog application found; native selected-vehicle fitment remains unverified."
                )
        else:
            result.reasons.append(
                "No verified application; missing records or blocked sources are not incompatibility."
            )
        if product["status"] != "identified":
            result.status = "needs_confirmation"
            result.warnings.append(
                "Supplied part identity was not verified against the selected Amazon ASIN."
            )
        if not vehicle.check_digit_matches or set(vehicle.error_codes) != {"0"}:
            result.status = "needs_confirmation"
            result.reasons.append("Vehicle decode must be valid before automatic compatibility.")
        return result
