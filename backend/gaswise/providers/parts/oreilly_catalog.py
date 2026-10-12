"""Discover exact retailer products from public sitemaps, then verify JSON identities.

The compressed URL documents are a bounded, expiring cache, not a fitment database.
"""

import asyncio
import gzip
import io
import json
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from gaswise.providers.parts.product import brand_key, compact

ROOT = "https://www.oreillyauto.com"


def sitemap_urls(body):
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    return [e.text for e in root.iter() if e.tag.endswith("}loc") and e.text]


def unpack(body):
    if body.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
            body = stream.read(24_000_001)
    if len(body) > 24_000_000:
        raise ValueError("sitemap_expansion_limit")
    return body


def candidates(documents, product):
    numbers = {compact(n): n for n in product["identifiers"]}
    result = {}
    for body in documents:
        for url in sitemap_urls(unpack(body)):
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "www.oreillyauto.com"
                or parsed.query
                or parsed.fragment
            ):
                continue
            segments = parsed.path.split("/")
            if not parsed.path.startswith("/detail/c/") or len(segments) < 6 or ".." in segments:
                continue
            number = compact(segments[-1])
            line = re.fullmatch(r"([a-zA-Z]{2,8})\d+", segments[-2])
            if number not in numbers or not line:
                continue
            result[(line[1].upper(), number)] = url
            if len(result) > 12:
                return {}  # Ambiguous number, never enumerate arbitrary manufacturer codes.
    return result


class OReillyCatalog:
    def __init__(self):
        self.documents = []
        self.expires = 0
        self.lock = asyncio.Lock()

    async def discover(self, reader, product):
        async with self.lock:
            if time.monotonic() >= self.expires:
                raw = await reader.read(ROOT + "/sitemap.xml", headers={"Accept": "application/xml"})
                urls = sitemap_urls(raw or "")
                if not urls or len(urls) > 20:
                    return None
                documents, size = [], 0
                for url in urls:
                    parsed = urlsplit(url)
                    if parsed.netloc != "www.oreillyauto.com" or not re.fullmatch(
                        r"/sitemap\d+\.xml\.gz", parsed.path
                    ):
                        return None
                    body = await reader.read_sitemap(url)
                    if not body:
                        return None
                    size += len(body)
                    if size > 25_000_000:
                        return None
                    documents.append(body)
                self.documents, self.expires = documents, time.monotonic() + 3600
        try:
            rows = await asyncio.to_thread(candidates, self.documents, product)
        except (ValueError, OSError, EOFError):
            return None
        verified = []
        keys = list(rows)
        for offset in range(0, len(keys), 4):
            batch = keys[offset : offset + 4]
            raw = await reader.read(
                ROOT + "/pcp/compare-items",
                params={"compares": ",".join(f"{line}-{number}" for line, number in batch)},
                headers={"Accept": "application/json"},
            )
            try:
                data = json.loads(raw or "null")
            except ValueError:
                continue
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                key = (item.get("lineCode"), compact(item.get("itemNumber")))
                name = item.get("productName", "")
                if key not in batch or not isinstance(name, str):
                    continue
                tokens = name.split()
                if any(
                    brand_key(" ".join(tokens[:n])) == brand_key(product["brand"])
                    for n in range(1, min(4, len(tokens)) + 1)
                ):
                    verified.append(
                        {
                            "url": rows[key],
                            "part": {"lineCode": key[0], "itemNumber": item["itemNumber"]},
                            "name": name,
                        }
                    )
        return verified[0] if len(verified) == 1 else None
