"""Generic product identity from the selected Amazon item's labeled fields."""

import re
from html.parser import HTMLParser


def compact(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper()) if isinstance(value, str) else ""


def clean(value):
    return " ".join(value.replace("\u200e", "").replace("\u200f", "").split()).strip()


class ProductHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self.asins = set()
        self.title = []
        self.title_depth = 0
        self.table_depth = 0
        self.details_depth = 0
        self.cell = None
        self.key, self.value = [], []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "span" and attrs.get("id") == "productTitle":
            self.title_depth = 1
        elif self.title_depth:
            self.title_depth += 1
        if tag == "input" and attrs.get("name", "").upper() == "ASIN":
            self.asins.add(attrs.get("value", ""))
        if tag == "table":
            self.table_depth += 1
            if "prodDetTable" in attrs.get("class", "").split() or attrs.get("id", "").startswith(
                "productDetails_"
            ):
                self.details_depth = self.table_depth
        if self.details_depth:
            if tag == "tr":
                self.key, self.value = [], []
            if tag in {"th", "td"}:
                self.cell = tag

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if self.title_depth:
            self.title_depth -= 1
        if self.details_depth and tag == "tr":
            key, value = clean(" ".join(self.key)), clean(" ".join(self.value))
            if key and value:
                self.fields.setdefault(compact(key), set()).add(value)
        if tag in {"th", "td"}:
            self.cell = None
        if tag == "table":
            if self.details_depth == self.table_depth:
                self.details_depth = 0
            self.table_depth = max(0, self.table_depth - 1)

    def handle_data(self, data):
        if self.hidden:
            return
        if self.title_depth:
            self.title.append(data)
        if self.details_depth and self.cell:
            (self.key if self.cell == "th" else self.value).append(data)


def identify_amazon(html, url):
    result = {
        "status": "unavailable",
        "source_url": url,
        "brand": None,
        "mpn": None,
        "model_number": None,
        "title": None,
        "category": None,
        "identifiers": [],
    }
    if not html:
        return result
    parsed = ProductHTML()
    parsed.feed(html)
    result["title"] = clean(" ".join(parsed.title)) or None
    if not result["title"]:
        return result

    def one(*keys):
        values = set()
        for key in keys:
            values.update(parsed.fields.get(compact(key), set()))
        if len({compact(v) for v in values}) != 1:
            return None
        return sorted(values)[0] if values else None

    asin = url.rsplit("/", 1)[-1]
    table_asin = one("ASIN")
    if table_asin != asin or parsed.asins != {asin}:
        result["status"] = "ambiguous"
        return result
    result.update(
        brand=one("Brand Name", "Brand"),
        mpn=one("Manufacturer Part Number"),
        model_number=one("Model Number", "Item model number"),
        category=one("Item Type Name"),
    )
    if not result["brand"] or not (result["mpn"] or result["model_number"]):
        result["status"] = "ambiguous"
        return result
    result["identifiers"] = list(dict.fromkeys(v for v in [result["mpn"], result["model_number"]] if v))
    result["status"] = "identified"
    return result


def brand_key(value):
    # Normalize company descriptors; exact part identifiers are still mandatory.
    text = re.sub(
        r"\b(?:filters?|engineering|automotive|inc|llc|ltd)\b",
        "",
        value if isinstance(value, str) else "",
        flags=re.I,
    )
    return compact(text) or compact(value)
