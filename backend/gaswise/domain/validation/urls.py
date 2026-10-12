"""Pure URL validation shared by contracts and external adapters."""

import re
from urllib.parse import urlsplit


def amazon_url(value):
    parsed = urlsplit(value)
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)", parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"amazon.com", "www.amazon.com"}
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or not match
    ):
        raise ValueError("A US Amazon HTTPS product URL containing an ASIN is required")
    return "https://www.amazon.com/dp/" + match[1]


def validate_oreilly_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.oreillyauto.com"
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/detail/c/")
        or ".." in parsed.path.split("/")
    ):
        raise ValueError("A canonical OReilly HTTPS product detail URL is required")
    return url


def validate_hertz_listing_url(url):
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise ValueError("hertz_invalid_listing_url") from None
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.hertzcarsales.com"
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith(".htm")
        or not parsed.path.startswith(("/used/", "/certified/", "/rent2buy/"))
    ):
        raise ValueError("hertz_invalid_listing_url")
    return url
