"""One optional public listing read; dealer grades never establish numeric octane."""

import re
from html.parser import HTMLParser

import httpx

from gaswise.domain.ports import ProviderError
from gaswise.domain.validation.urls import validate_hertz_listing_url


def validate_listing_url(url):
    try:
        return validate_hertz_listing_url(url)
    except ValueError:
        raise ProviderError("hertz_invalid_listing_url") from None


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


class HertzProvider:
    def __init__(self, client, public_http=None):
        self.client = client
        self.public_http = public_http

    async def listing(self, url):
        validate_listing_url(url)
        if self.public_http is not None:
            html = await self.public_http.read(url, max_bytes=2_000_000)
            if html is None:
                raise ProviderError("hertz_unavailable")
            return self.parse_listing(html)
        try:
            async with self.client.stream(
                "GET", url, follow_redirects=False, headers={"Accept": "text/html"}
            ) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ProviderError("hertz_unavailable")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ProviderError("hertz_invalid_response")
                    chunks.append(chunk)
        except httpx.HTTPError:
            raise ProviderError("hertz_unavailable") from None
        return self.parse_listing(b"".join(chunks).decode("utf-8", errors="replace"))

    @staticmethod
    def parse_listing(html):
        parser = VisibleText()
        parser.feed(html)
        text = " ".join(" ".join(parser.parts).split())
        grades = set(
            re.findall(r"Recommended fuel\s*:\s*(Regular Unleaded|Premium Unleaded|Diesel)", text, re.I)
        )
        vins = set(re.findall(r"\bVIN\s*:?\s*([A-HJ-NPR-Z0-9]{17})\b", text, re.I))
        if len(grades) != 1 or len(vins) != 1:
            raise ProviderError("hertz_ambiguous_listing")
        return next(iter(vins)).upper(), next(iter(grades)).lower()
