"""Supplier interchange discovery: replacement candidates, never automatic fitment."""

import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit

from gaswise.providers.parts.product import compact

ROOT = "https://www.oreillyauto.com"


def decoded(raw):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


class InterchangeHTML(HTMLParser):
    def __init__(self, number, manufacturers):
        super().__init__()
        self.number, self.manufacturers = number, set(manufacturers)
        self.rows, self.current = [], None
        self.heading = False
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "product--interchange" in attrs.get("class", "").split():
            self.current = {"title": [], "links": [], "references": [], "identity": ""}
        if self.current is None:
            return
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "h3":
            self.heading = True
        if tag == "input" and attrs.get("id", "").startswith("compare"):
            self.current["identity"] = attrs["id"][len("compare") :]
        if tag == "a":
            url = attrs.get("href", "")
            parsed = urlsplit(url)
            if parsed.netloc not in {"", "www.oreillyauto.com"}:
                return
            if parsed.path.startswith("/detail/c/"):
                self.current["links"].append(ROOT + parsed.path)
            query = parse_qs(parsed.query)
            if (
                parsed.path == "/search/cross-reference"
                and query.get("partNumber") == [self.number]
                and len(query.get("manufacturerFilter", [])) == 1
                and query["manufacturerFilter"][0] in self.manufacturers
            ):
                self.current["references"].append(query["manufacturerFilter"][0])

    def handle_data(self, data):
        if self.current is not None and self.heading and not self.hidden:
            self.current["title"].append(data)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "h3":
            self.heading = False
        if tag == "article" and self.current is not None:
            row = self.current
            title = " ".join(" ".join(row["title"]).split())
            match = re.fullmatch(r"([A-Z0-9]+)-([A-Z0-9 .-]+)", row["identity"])
            links = list(dict.fromkeys(row["links"]))
            if match and row["references"] and len(links) == 1 and compact(title).endswith(compact(match[2])):
                self.rows.append(
                    {
                        "title": title,
                        "line_code": match[1],
                        "part_number": match[2],
                        "product_url": links[0],
                        "reference_part_number": self.number,
                        "reference_manufacturer": row["references"][0],
                    }
                )
            self.current = None


async def verify_candidate_identities(reader, candidates):
    """Public comparison metadata accepts at most four LCINs; no inferred line codes."""
    verified = {}
    for offset in range(0, min(len(candidates), 24), 4):
        batch = candidates[offset : offset + 4]
        expected = {(r["line_code"], r["part_number"]) for r in batch}
        compares = ",".join(f"{line}-{number}" for line, number in sorted(expected))
        data = decoded(
            await reader.read(
                ROOT + "/pcp/compare-items",
                params={"compares": compares},
                headers={"Accept": "application/json"},
            )
        )
        if not isinstance(data, list) or len(data) > 4:
            continue
        seen = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            line, number, name = item.get("lineCode"), item.get("itemNumber"), item.get("productName")
            if not isinstance(line, str) or not isinstance(number, str):
                continue
            identity = (line, number)
            if identity in expected and isinstance(name, str) and name.strip():
                if identity in seen:
                    verified.pop(identity, None)
                else:
                    verified[identity] = name
                seen.add(identity)
    return [
        {
            **r,
            "identity_status": "verified" if (r["line_code"], r["part_number"]) in verified else "unverified",
            **(
                {"catalog_product_name": verified[(r["line_code"], r["part_number"])]}
                if (r["line_code"], r["part_number"]) in verified
                else {}
            ),
        }
        for r in candidates
    ]


async def discover_interchanges(reader, product):
    numbers = list(dict.fromkeys(compact(n) for n in product["identifiers"] if compact(n)))[:2]
    fallback = None
    for number in numbers:
        result = await discover_number(reader, number)
        if result["replacement_candidates"]:
            return result
        if fallback is None or len(result["lookup_stages"]) > len(fallback["lookup_stages"]):
            fallback = result
    return fallback


async def discover_number(reader, number):
    result = {
        "source": "oreilly",
        "scope": "catalog_application",
        "status": "unavailable",
        "source_url": ROOT + "/interchange/getPartTypes",
        "product_relation": "interchange_candidate",
        "referenced_part_number": number,
        "replacement_candidates": [],
        "lookup_stages": [],
    }
    headers = {"Accept": "application/json, text/plain, */*", "Referer": ROOT + "/", "Origin": ROOT}
    data = decoded(
        await reader.read(ROOT + "/interchange/getPartTypes", params={"partNumber": number}, headers=headers)
    )
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        result["detail"] = (
            "Interchange part-type lookup unavailable; this does not reject the requested product."
        )
        return result
    ids = [
        r.get("id")
        for r in rows
        if isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"].isdigit()
    ]
    if len(ids) != len(rows):
        return result
    result["lookup_stages"].append("part_types")
    params = {"q": number, "partNumber": number, "partTypeIds": ids}
    data = decoded(
        await reader.read(ROOT + "/interchange/getManufacturers", json_body=params, headers=headers)
    )
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        result["detail"] = "Interchange manufacturer candidates unavailable."
        return result
    manufacturers = [
        r.get("id") for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"].strip()
    ]
    if len(manufacturers) != len(rows):
        return result
    result["lookup_stages"].append("manufacturer_candidates")
    query = {**params, "partTypeIds": ",".join(ids), "manufacturers": ",".join(manufacturers)}
    url = ROOT + "/search/cross-reference?" + urlencode(query)
    result["source_url"] = result["interchange_source_url"] = url
    html = await reader.read(ROOT + "/search/cross-reference", params=query, headers={"Accept": "text/html"})
    parser = InterchangeHTML(number, manufacturers)
    parser.feed(html or "")
    result["replacement_candidates"] = parser.rows[:24]
    if parser.rows:
        result["status"] = "conditional"
        result["lookup_stages"].append("replacement_candidates")
        result["replacement_candidates"] = await verify_candidate_identities(
            reader, result["replacement_candidates"]
        )
        if any(r["identity_status"] == "verified" for r in result["replacement_candidates"]):
            result["lookup_stages"].append("product_identities")
        result["detail"] = (
            "Supplier interchange candidates found across brands; each requires its own vehicle application check. Manufacturer choices alone do not identify the Amazon brand."
        )
    else:
        result["detail"] = (
            "Interchange type/manufacturer API succeeded, but the results page supplied no readable replacement SKUs; vehicle fitment remains unverified."
        )
    return result
