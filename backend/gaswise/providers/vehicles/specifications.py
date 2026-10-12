"""Bounded anonymous public spec reads; no PDF, login, retry or listing majority vote."""

import asyncio
import json
import re
import time
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from gaswise.contracts.vehicles import FuelSpecificationEvidence
from gaswise.domain.ports import ProviderError
from gaswise.providers.http.httpx_public import HTTPXPublicReader
from gaswise.providers.vehicles.hertz import validate_listing_url


class SpecHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.scripts, self.links, self.headings = [], [], [], []
        self.script = None
        self.hidden = False
        self.h1 = False
        self.selected_options = []
        self.selected = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.script = []
        if tag == "style":
            self.hidden = True
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "h1":
            self.h1 = True
        if tag == "option":
            self.selected = "selected" in attrs

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag == "style":
            self.hidden = False
        if tag == "h1":
            self.h1 = False
        if tag == "option":
            self.selected = False

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        elif not self.hidden:
            self.parts.append(data)
            if self.h1:
                self.headings.append(data)
            if self.selected:
                self.selected_options.append(data)


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def family(vehicle):
    # URL discovery only; configuration matching still checks year, engine, cylinders and drive.
    return vehicle.model.split()[0]


def grade(label):
    text = label.lower()
    return (
        "premium"
        if "premium" in text
        else "midgrade"
        if "midgrade" in text
        else "regular"
        if "regular" in text
        else "diesel"
        if text == "diesel"
        else None
    )


def fact(text, pattern):
    match = re.search(pattern, text, re.I)
    return match.group(1) if match else None


def technical_match(vehicle, engine, cylinders, drive, transmission):
    from gaswise.domain.vehicles.matching import drive_class

    def speeds(value):
        match = re.search(r"(\d+)[ -]*speed|(\d+)-spd|\(S(\d+)\)", value, re.I)
        return next((int(v) for v in match.groups() if v), None) if match else None

    actual_speed, expected_speed = speeds(transmission or ""), speeds(vehicle.transmission)
    drive = re.sub(r"\s+", "-", drive or "")
    actual_manual = (
        "manual" in (transmission or "").lower() and "automatic" not in (transmission or "").lower()
    )
    expected_manual = "manual" in vehicle.transmission.lower()
    return (
        engine is not None
        and cylinders is not None
        and drive is not None
        and vehicle.engine_liters == Decimal(engine)
        and vehicle.cylinders == int(cylinders)
        and drive_class(drive) is not None
        and drive_class(drive) == drive_class(vehicle.drive)
        and actual_speed is not None
        and actual_speed == expected_speed
        and actual_manual == expected_manual
    )


def parse_specs(html, vehicle, source, url):
    try:
        return _parse_specs(html, vehicle, source, url)
    except (TypeError, ValueError, KeyError, AttributeError, InvalidOperation):
        return FuelSpecificationEvidence(
            source=source,
            source_group="edmunds_specs" if source == "edmunds" else "dealer_specs",
            source_url=url,
            status="ambiguous",
        )


def _parse_specs(html, vehicle, source, url):
    parsed = SpecHTML()
    parsed.feed(html)
    text = " ".join(" ".join(parsed.parts).split())
    heading = " ".join(parsed.headings)
    base = dict(
        source=source, source_group="edmunds_specs" if source == "edmunds" else "dealer_specs", source_url=url
    )
    label = None
    if source == "edmunds":
        # Restrict facts to the specs block, excluding inventory and related vehicle text.
        start = text.lower().find("fuel & mpg")
        end = text.lower().find("suspension", start)
        block = text[start:end] if start >= 0 and end > start else ""
        label = fact(
            block,
            r"Fuel type\s+(Regular unleaded|Premium unleaded(?:\s*\((?:recommended|required)\))?|Midgrade unleaded|Diesel)",
        )
        engine = fact(block, r"Base engine size\s+([0-9.]+)\s*L")
        cylinders = fact(block, r"Cylinders\s+(?:Inline\s*|V\s*)?(\d+)")
        drive = fact(block, r"Drive type\s+((?:front|rear|all|four)[ -]wheel(?: drive)?)")
        transmission = fact(
            block, r"Transmission\s+((?:\d+[ -]speed)[^<>]*?)(?=Drive type|Suspension|Rear |Front |$)"
        )
        selected_description = (
            " ".join(parsed.selected_options)
            or fact(text[:start], r"Most Popular\s+(.{1,160}?)Est\. Market Value")
            or ""
        )
    else:
        facts = {}
        identities = []
        for script in parsed.scripts:
            try:
                obj = json.loads(script)
                items = obj if isinstance(obj, list) else [obj]
                identities.extend(i for i in items if isinstance(i, dict) and "vehicleModelDate" in i)
            except ValueError:
                pass
            match = re.search(r"DDC\.WS\.state\['ws-detailed-specs'\]\['detailed-specs1'\]\s*=\s*", script)
            if match:
                try:
                    obj, _ = json.JSONDecoder().raw_decode(script[match.end() :])
                    for row in obj["equipment"]["specification"]:
                        spec = row.get("spec") if isinstance(row, dict) else None
                        if (
                            isinstance(spec, dict)
                            and isinstance(spec.get("description"), str)
                            and isinstance(spec.get("detail"), str)
                        ):
                            facts[spec["description"].lower()] = spec["detail"]
                except (ValueError, KeyError, TypeError):
                    pass
        if len(identities) != 1:
            return FuelSpecificationEvidence(**base, status="ambiguous")
        identity = identities[0]
        brand = identity.get("brand", {})
        brand = brand.get("name", "") if isinstance(brand, dict) else brand
        if (
            str(identity["vehicleModelDate"]) != str(vehicle.year)
            or normalize(brand) != normalize(vehicle.make)
            or normalize(identity.get("model", "")) != normalize(family(vehicle))
        ):
            return FuelSpecificationEvidence(**base, status="mismatch")
        label = facts.get("recommended fuel") or identity.get("fuelType")
        engine = fact(facts.get("engine liters", ""), r"([0-9.]+)\s*L")
        cylinders = fact(facts.get("cylinder configuration", ""), r"[IVH][ -]?(\d+)")
        drive = facts.get("drive type") or identity.get("driveWheelConfiguration")
        transmission = facts.get("transmission")
        selected_description = identity.get("name", "")
    heading_valid = (
        str(vehicle.year) in heading
        and normalize(vehicle.make) in normalize(heading)
        and re.search(r"(?<!\w)" + re.escape(family(vehicle)) + r"(?!\w)", heading, re.I)
    )
    if not heading_valid or not technical_match(vehicle, engine, cylinders, drive, transmission):
        return FuelSpecificationEvidence(**base, status="mismatch")
    if not label or not grade(label):
        return FuelSpecificationEvidence(**base, status="ambiguous")
    # Qualifiers such as Type R / Competition cannot be inferred from a family's default trim.
    qualifiers = re.sub(
        r"\b(?:coupe|convertible|sedan|awd|2wd|4wd|4matic|le/se|xle/xse)\b",
        "",
        vehicle.model[len(family(vehicle)) :],
        flags=re.I,
    ).strip()
    if qualifiers and normalize(qualifiers) not in normalize(selected_description):
        return FuelSpecificationEvidence(**base, status="mismatch")
    return FuelSpecificationEvidence(
        **base,
        status="matched",
        fuel_grade=grade(label),
        observed_label=label,
        requirement="required"
        if "required" in label.lower()
        else "recommended"
        if source == "hertz" or "recommended" in label.lower()
        else "unspecified",
    )


class SpecificationProvider:
    def __init__(self, client, public_http=None):
        self.client = client
        self.public_http = public_http
        self.cache = OrderedDict()
        self.lock = asyncio.Lock()

    async def html(self, url, params=None):
        reader = self.public_http or HTTPXPublicReader(self.client)
        return await reader.read(url, params=params)

    async def observations(self, vehicle):
        key = (
            vehicle.year,
            vehicle.make,
            vehicle.model,
            vehicle.engine_liters,
            vehicle.cylinders,
            vehicle.drive,
            vehicle.transmission,
        )
        async with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < cached[1]:
                self.cache.move_to_end(key)
                return [v.model_copy(deep=True) for v in cached[2]]
            result = await asyncio.gather(self.edmunds(vehicle), self.hertz(vehicle))
            ttl = 86400 if any(v.status == "matched" for v in result) else 900
            self.cache[key] = (time.monotonic(), ttl, result)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
            return [v.model_copy(deep=True) for v in result]

    async def edmunds(self, vehicle):
        if self.public_http is not None:
            return await self.edmunds_api(vehicle)
        make = vehicle.make.lower().replace(" ", "-")
        model = family(vehicle).lower()
        url = f"https://www.edmunds.com/{make}/{model}/{vehicle.year}/features-specs/"
        html = await self.html(url)
        return (
            parse_specs(html, vehicle, "edmunds", url)
            if html and ("Fuel &amp; MPG" in html or "Fuel & MPG" in html)
            else FuelSpecificationEvidence(
                source="edmunds", source_group="edmunds_specs", source_url=url, status="unavailable"
            )
        )

    async def hertz(self, vehicle):
        if self.public_http is not None:
            return await self.hertz_inventory(vehicle)
        url = "https://www.hertzcarsales.com/used-cars-for-sale.htm"
        html = await self.html(url, {"make": vehicle.make, "model": family(vehicle), "year": vehicle.year})
        base = dict(source="hertz", source_group="dealer_specs", source_url=url)
        if not html:
            return FuelSpecificationEvidence(**base, status="unavailable")
        parsed = SpecHTML()
        parsed.feed(html)
        paths = set()
        for path in parsed.links:
            candidate = urljoin(url, path)
            try:
                validate_listing_url(candidate)
            except ProviderError:
                continue
            target = urlsplit(candidate).path
            if f"/{vehicle.year}-" in target and normalize(family(vehicle)) in normalize(target):
                paths.add(candidate)
        if not paths:
            return FuelSpecificationEvidence(**base, status="unavailable")
        # One detail per discovery, never unbounded inventory crawling.
        listing = sorted(paths)[0]
        html = await self.html(listing)
        return (
            parse_specs(html, vehicle, "hertz", listing)
            if html
            else FuelSpecificationEvidence(**base, status="unavailable")
        )

    async def hertz_inventory(self, vehicle):
        url = "https://www.hertzcarsales.com/api/widget/ws-inv-data/getInventoryAndFacets"
        base = dict(source="hertz", source_group="dealer_specs", source_url=url)
        body = {
            "siteId": "hertzcarsales",
            "locale": "en_US",
            "device": "DESKTOP",
            "pageAlias": "INVENTORY_LISTING_GRID_AUTO_ALL",
            "pageId": "hertzcarsales_SITEBUILDER_INVENTORY_SEARCH_RESULTS_AUTO_USED_V1_196",
            "windowId": "inventory-data-bus2",
            "widgetName": "ws-inv-data",
            "inventoryParameters": {
                "make": [vehicle.make],
                "model": [family(vehicle)],
                "year": [str(vehicle.year)],
            },
            "preferences": {
                "listing.config.id": "auto-used,auto-r2b",
                "pageSize": "2",
                "disableGeodistSort": "true",
            },
            "includePricing": True,
        }
        raw = await self.public_http.read(url, json_body=body)
        try:
            rows = json.loads(raw)["inventory"]
            if not isinstance(rows, list):
                raise ValueError("invalid_inventory")
        except (TypeError, ValueError, KeyError):
            return FuelSpecificationEvidence(**base, status="unavailable")
        for row in rows[:2]:
            if not isinstance(row, dict):
                continue
            if (
                str(row.get("year")) != str(vehicle.year)
                or normalize(str(row.get("make", ""))) != normalize(vehicle.make)
                or normalize(str(row.get("model", ""))) != normalize(family(vehicle))
            ):
                continue
            link = row.get("link")
            if not isinstance(link, str):
                continue
            listing = urljoin(url, link)
            try:
                validate_listing_url(listing)
            except ProviderError:
                continue
            # One detail at most; matching all physical constraints happens in parse_specs.
            html = await self.html(listing)
            return (
                parse_specs(html, vehicle, "hertz", listing)
                if html
                else FuelSpecificationEvidence(**base, status="unavailable")
            )
        return FuelSpecificationEvidence(**base, status="unavailable")

    async def edmunds_api(self, vehicle):
        make, model = vehicle.make.lower().replace(" ", "-"), family(vehicle).lower()
        page = f"https://www.edmunds.com/{make}/{model}/{vehicle.year}/features-specs/"
        headers = {"Accept": "application/json", "Referer": page}
        base = dict(source="edmunds", source_group="edmunds_specs", source_url=page)
        root = "https://www.edmunds.com/gateway/api/vehicle"
        raw = await self.public_http.read(
            root + "/v3/modelYears",
            headers=headers,
            params={
                "makeNiceId": make,
                "modelNiceId": model,
                "year": vehicle.year,
                "pageSize": 50,
                "pageNum": 1,
            },
        )
        try:
            data = json.loads(raw)
            infos = data["results"]
            if not isinstance(infos, list) or len(infos) != 1 or data.get("totalPages") != 1:
                raise ValueError("nonunique_metadata")
            info = infos[0]
            if (
                info.get("makeNiceId") != make
                or info.get("modelNiceId") != model
                or info.get("year") != vehicle.year
            ):
                return FuelSpecificationEvidence(**base, status="mismatch")
            allowed_styles = {
                r["id"] for r in info["styles"] if isinstance(r, dict) and isinstance(r.get("id"), int)
            }
            submodels = info["submodels"]
            if not allowed_styles or not isinstance(submodels, list) or not submodels:
                raise ValueError("missing_metadata")
        except (ValueError, TypeError, KeyError, AttributeError):
            return FuelSpecificationEvidence(**base, status="unavailable")
        checked, seen = 0, set()
        for submodel in submodels:
            if not isinstance(submodel, dict):
                continue
            sub = submodel.get("niceId")
            if not isinstance(sub, str) or not re.fullmatch(r"[a-z0-9-]{1,80}", sub) or sub in seen:
                continue
            seen.add(sub)
            if sub == "plug-in-hybrid":
                continue
            if checked >= 3:
                break
            checked += 1
            url = f"{root}/v5/makes/{make}/models/{model}/submodels/{sub}/years/{vehicle.year}/styles/features-specs"
            raw = await self.public_http.read(
                url,
                headers=headers,
                params={
                    "pageNum": 1,
                    "pageSize": 50,
                    "sortby": "price:asc",
                    "fields": "styleAttributes,features.standard.Drive Train,features.standard.Engine,features.standard.Fuel",
                },
            )
            try:
                data = json.loads(raw)
                expected = f"#/makes/{make}/models/{model}/submodels/{sub}/years/{vehicle.year}/styles/partial-features-specs"
                if data.get("$dataset") != expected or data.get("totalPages") != 1:
                    continue
                rows = data["results"]
                if not isinstance(rows, list) or len(rows) > 50:
                    continue
                matches = [
                    parse_edmunds_style(row, vehicle, url)
                    for row in rows
                    if isinstance(row, dict) and row.get("id") in allowed_styles
                ]
                matches = [m for m in matches if m.status == "matched"]
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
            if matches:
                if len({(m.fuel_grade, m.requirement) for m in matches}) != 1:
                    return FuelSpecificationEvidence(**base, status="ambiguous")
                return matches[0]
        return FuelSpecificationEvidence(**base, status="mismatch" if checked else "unavailable")


def parse_edmunds_style(row, vehicle, url):
    base = dict(source="edmunds", source_group="edmunds_specs", source_url=url)
    try:
        name = row["name"]
        attrs = row["styleAttributes"]
        if (
            not isinstance(name, str)
            or not isinstance(attrs, dict)
            or attrs.get("electric") is not False
            or attrs.get("pluginElectric") is not False
        ):
            return FuelSpecificationEvidence(**base, status="mismatch")
        standard = row["features"]["standard"]

        def category(key):
            return {
                r["name"]: r["value"]
                for r in standard.get(key, [])
                if isinstance(r, dict) and isinstance(r.get("name"), str) and isinstance(r.get("value"), str)
            }

        engine, drive, fuel = category("Engine"), category("Drive Train"), category("Fuel")
        liters = fact(engine.get("Base engine size", ""), r"([0-9.]+)\s*L")
        cylinders = fact(engine.get("Cylinders", ""), r"(\d+)")
        if not technical_match(
            vehicle, liters, cylinders, drive.get("Drive type"), drive.get("Transmission")
        ):
            return FuelSpecificationEvidence(**base, status="mismatch")
        qualifiers = re.sub(
            r"\b(?:awd|2wd|4wd|4matic|le/se|xle/xse)\b", "", vehicle.model[len(family(vehicle)) :], flags=re.I
        ).strip()
        if any(
            not re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", name, re.I)
            for token in re.findall(r"[a-zA-Z0-9]+", qualifiers)
        ):
            return FuelSpecificationEvidence(**base, status="mismatch")
        label = fuel.get("Fuel type", "")
        if not grade(label):
            return FuelSpecificationEvidence(**base, status="ambiguous")
        return FuelSpecificationEvidence(
            **base,
            status="matched",
            fuel_grade=grade(label),
            observed_label=label,
            requirement="required"
            if "required" in label.lower()
            else "recommended"
            if "recommended" in label.lower()
            else "unspecified",
        )
    except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
        return FuelSpecificationEvidence(**base, status="ambiguous")
