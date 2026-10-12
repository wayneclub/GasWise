"""Public retailer application protocol, exact identities only; blocked reads fail soft."""

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from gaswise.domain.validation.urls import validate_oreilly_url as validate_oreilly_url
from gaswise.providers.parts.discovery import category_pages, search_terms
from gaswise.providers.parts.interchange import discover_interchanges
from gaswise.providers.parts.product import clean, compact

ROOT = "https://www.oreillyauto.com"


def exact_product_links(html, product):
    parsed = RetailerHTML()
    parsed.feed(html or "")
    urls = set()
    for link in parsed.links:
        observed = urlsplit(urljoin(ROOT, link))
        url = observed._replace(query="", fragment="").geturl()
        try:
            validate_oreilly_url(url)
        except ValueError:
            continue
        if compact(observed.path.split("/v/")[0].rsplit("/", 1)[-1]) in {
            compact(n) for n in product["identifiers"]
        }:
            urls.add(url)
    return urls


class RetailerHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.text, self.titles = [], [], []
        self.hidden = 0
        self.h1 = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "h1":
            self.h1 = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "h1":
            self.h1 = False

    def handle_data(self, value):
        if not self.hidden:
            self.text.append(value)
            if self.h1:
                self.titles.append(value)


def parse_product(html, product):
    parsed = RetailerHTML()
    parsed.feed(html or "")
    text, heading = clean(" ".join(parsed.text)), clean(" ".join(parsed.titles))
    match = re.search(r"Part\s*#\s*:?\s*([A-Z0-9 /.-]+?)\s+Line\s*:\s*([A-Z0-9]+)", text, re.I)
    if not match or not heading:
        return None
    number, line = clean(match[1]), match[2]
    if compact(number) not in {compact(n) for n in product["identifiers"]}:
        return None
    # Brand must be observed in the product heading, not inferred from URL/search similarity.
    if not re.match(re.escape(product["brand"]) + r"(?:\s|\b)", heading, re.I):
        return None
    return {"itemNumber": number, "lineCode": line}


def parse_applications(data, vehicle):
    if not isinstance(data, dict) or not isinstance(data.get("compatibleModels"), dict):
        return "unavailable", [], []
    matches = []
    names = [v for v in (vehicle.trim, vehicle.model) if v]
    for description, years in list(data["compatibleModels"].items())[:1000]:
        if not isinstance(description, str) or not isinstance(years, list) or vehicle.year not in years:
            continue
        if not any(
            re.match(re.escape(n).replace(r"\ ", r"\s*") + r"(?:\s|$)", description, re.I) for n in names
        ):
            continue
        liters = re.search(r"([0-9.]+)L\b", description, re.I)
        cylinders = re.search(r"\b(?:V|L|I|H)(\d+)\b", description, re.I)
        if not liters or not cylinders or vehicle.engine_liters is None or vehicle.cylinders is None:
            continue
        if (
            abs(float(liters[1]) - float(vehicle.engine_liters)) > 0.06
            or int(cylinders[1]) != vehicle.cylinders
        ):
            continue
        matches.append(description)
    if not matches:
        return "no_match", [], []
    # Application text is useful but does not execute the selected-engine checkfit protocol.
    return (
        "conditional",
        matches,
        ["Selected-engine checkfit and any required vehicle attributes remain unverified."],
    )


class OReillyParts:
    def __init__(self, reader, catalog=None):
        self.reader = reader
        self.catalog = catalog

    async def assess(self, product, vehicle, product_url=None, identity=None):
        transport = getattr(self.reader, "public_http", None)
        if transport is not None and hasattr(transport, "oreilly_session"):
            async with transport.oreilly_session() as session:
                if identity is not None and hasattr(session, "vin_configuration"):
                    await session.vin_configuration(
                        identity.vin, year=vehicle.year, make=vehicle.make, model=vehicle.model
                    )
                result = await OReillyParts(session, getattr(transport, "oreilly_catalog", None))._assess(
                    product, vehicle, product_url
                )
                result["lookup_stages"] = [*session.stages, *result.get("lookup_stages", [])]
                if session.failure:
                    result["provider_error"] = session.failure
                return result
        return await self._assess(product, vehicle, product_url)

    async def _assess(self, product, vehicle, product_url=None):
        base = {"source": "oreilly", "scope": "catalog_application", "source_url": ROOT + "/search"}
        catalog_product = None
        if not product_url:
            stages, urls = [], set()
            for term in search_terms(product):
                html = await self.reader.read(
                    ROOT + "/search", params={"q": term}, headers={"Accept": "text/html"}
                )
                stages.append("product_search")
                urls = exact_product_links(html, product)
                if urls:
                    break
                # A verification challenge will not be cleared by more search terms.
                if getattr(self.reader, "failure", None) == "browser_verification_required":
                    break
            if not urls:
                if self.catalog is not None:
                    catalog_product = await self.catalog.discover(self.reader, product)
                    stages.append("public_sitemap_identity_lookup")
                    if catalog_product:
                        urls.add(catalog_product["url"])
            if not urls:
                pages = await category_pages(self.reader, product)
                stages.append("category_fallback")
                for _, html in pages:
                    urls.update(exact_product_links(html, product))
            if len(urls) != 1:
                result = await discover_interchanges(self.reader, product)
                result["lookup_stages"] = list(dict.fromkeys([*stages, *result.get("lookup_stages", [])]))
                return result
            product_url = next(iter(urls))
            base["lookup_stages"] = list(dict.fromkeys(stages))
        validate_oreilly_url(product_url)
        if catalog_product:
            part = catalog_product["part"]
        else:
            html = await self.reader.read(product_url, headers={"Accept": "text/html"})
            part = parse_product(html, product)
        base["source_url"] = product_url
        if not part:
            return {
                **base,
                "status": "unavailable",
                "detail": "Product page blocked or exact brand/part identity not established.",
            }
        headers = {"Accept": "application/json, text/plain, */*", "Referer": product_url, "Origin": ROOT}
        raw = await self.reader.read(ROOT + "/product/compatible-makes", json_body=part, headers=headers)
        try:
            makes = json.loads(raw)["compatibleMakes"]
        except (ValueError, TypeError, KeyError):
            makes = None
        if not isinstance(makes, list) or not makes:
            return {
                **base,
                "status": "unavailable",
                "detail": "Public compatibility endpoint blocked, empty or unavailable.",
            }
        matching = [m for m in makes if isinstance(m, str) and compact(m) == compact(vehicle.make)]
        if len(matching) != 1:
            return {
                **base,
                "status": "incompatible" if not matching else "ambiguous",
                "detail": "Exact product application make does not match uniquely.",
            }
        raw = await self.reader.read(
            ROOT + "/product/compatible-models", json_body={**part, "makeName": matching[0]}, headers=headers
        )
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            data = None
        status, applications, conditions = parse_applications(data, vehicle)
        return {
            **base,
            "status": status,
            "conditions": conditions,
            "application_descriptions": applications,
            "part_number": part["itemNumber"],
            "brand": product["brand"],
            "detail": "Supplier model/year/engine applications; explicit checkfit is a separate protocol.",
        }
