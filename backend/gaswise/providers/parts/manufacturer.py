"""Public manufacturer interchange and independent application evidence.

Interchange selects candidates; application proof concerns the candidate, never
silently substitutes it for the requested product or claims retailer checkfit.
"""

import re
from html.parser import HTMLParser

from gaswise.providers.parts.product import brand_key, clean, compact

ROOT = "https://www2.wixfilters.com"


class Tables(HTMLParser):
    def __init__(self, table_id):
        super().__init__()
        self.table_id = table_id
        self.active = False
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("id") == self.table_id:
            self.active = True
        if self.active and tag == "tr":
            self.row = []
        if self.active and tag == "td":
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            if self.row is not None:
                self.row.append(clean(" ".join(self.cell)))
            self.cell = None
        if tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
        if tag == "table":
            self.active = False


def rows_from(html, table_id):
    parser = Tables(table_id)
    parser.feed(html or "")
    return parser.rows


def manufacturer_key(name):
    # Company spelling aliases only, not a part interchange database.
    key = brand_key(name)
    if key in {"MANNHUMMEL", "MANNBASE"}:
        return "MANN"
    return key


def wix_candidates(html, brand, identifiers):
    identifiers = {compact(x) for x in identifiers if compact(x)}
    candidates = []
    for row in rows_from(html, "gvPL"):
        if len(row) < 4:
            continue
        number, maker, target = row[1:4]
        if compact(number) not in identifiers or manufacturer_key(maker) != manufacturer_key(brand):
            continue
        if not re.fullmatch(r"[A-Za-z0-9-]{2,30}", target):
            continue
        candidate = {
            "brand": "WIX",
            "part_number": target,
            "reference_brand": maker,
            "reference_part_number": number,
            "relation": "interchange_candidate",
        }
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def assess_wix_applications(html, part_number, vehicle):
    if not re.search(r"Applications for part\s+" + re.escape(part_number) + r"\b", html or "", re.I):
        return {"status": "unavailable", "detail": "Manufacturer application identity did not echo."}
    rows = rows_from(html, "gvPartapps")
    matches = []
    uncertain = []
    names = {compact(x) for x in (vehicle.model, vehicle.trim) if x}
    for row in rows:
        if len(row) != 5:
            continue
        _, make, model, years, engine = row
        if compact(make) != compact(vehicle.make) or compact(model) not in names:
            continue
        period = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", years)
        if not period or not vehicle.year or not int(period[1]) <= vehicle.year <= int(period[2]):
            continue
        liters = re.search(r"\b(\d+(?:\.\d+)?)L\b", engine, re.I)
        cylinders = re.search(r"\b[VLHI](\d+)\b", engine, re.I)
        cc = re.search(r"\b(\d+)CC\b", engine, re.I)
        description = " | ".join(row[1:])
        if not liters or not cylinders or vehicle.engine_liters is None or vehicle.cylinders is None:
            uncertain.append(description)
            continue
        if abs(float(liters[1]) - vehicle.engine_liters) > 0.05 or int(cylinders[1]) != vehicle.cylinders:
            continue
        if cc and abs(int(cc[1]) / 1000 - vehicle.engine_liters) > 0.05:
            continue
        # Only recognized engine dimensions can establish an unrestricted application.
        remainder = re.sub(r"\b(?:[VLHI]\d+|\d+(?:\.\d+)?L|\d+CC|\d+CID)\b", "", engine, flags=re.I)
        if remainder.strip():
            uncertain.append(description)
        else:
            matches.append(description)
    if uncertain:
        return {
            "status": "conditional",
            "detail": "Application has unresolved engine data or restrictions.",
            "application_descriptions": list(dict.fromkeys(matches + uncertain)),
        }
    if matches:
        return {
            "status": "matched",
            "detail": "Manufacturer candidate application matches year, make, model, displacement and cylinders.",
            "matched_fields": ["year", "make", "model", "engine_liters", "cylinders"],
            "application_descriptions": list(dict.fromkeys(matches)),
        }
    return {
        "status": "no_match",
        "detail": "No matching candidate application in the returned manufacturer list.",
    }


class ManufacturerParts:
    def __init__(self, reader):
        self.reader = reader

    async def assess(self, product, vehicle):
        candidates = []
        for identifier in product.get("identifiers", [])[:2]:
            if not compact(identifier):
                continue
            html = await self.reader.read(ROOT + "/Lookup/Exactmatch.aspx", params={"PartNo": identifier})
            for candidate in wix_candidates(html, product.get("brand"), product.get("identifiers", [])):
                if candidate not in candidates:
                    candidates.append(candidate)
        targets = {compact(item["part_number"]) for item in candidates}
        if len(targets) > 1:
            return [
                {
                    "source": "manufacturer",
                    "scope": "engine_application",
                    "status": "ambiguous",
                    "source_url": ROOT + "/Lookup/Exactmatch.aspx",
                    "detail": "Manufacturer returned multiple replacement parts.",
                }
            ]
        results = []
        for candidate in candidates[:1]:
            html = await self.reader.read(
                ROOT + "/Lookup/PartApplications.aspx", params={"Part": candidate["part_number"]}
            )
            result = assess_wix_applications(html, candidate["part_number"], vehicle)
            results.append(
                dict(
                    candidate,
                    **result,
                    source="manufacturer",
                    scope="engine_application",
                    source_url=ROOT + "/Lookup/PartApplications.aspx?Part=" + candidate["part_number"],
                    reference_source_url=ROOT
                    + "/Lookup/Exactmatch.aspx?PartNo="
                    + compact(candidate["reference_part_number"]),
                )
            )
        return results
