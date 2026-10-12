"""Bounded discovery from observed product fields and retailer taxonomy links."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def search_terms(product):
    terms = [*product.get("identifiers", [])[:2]]
    if terms and product.get("brand"):
        terms.append(f"{product['brand']} {terms[0]}")
    terms.extend(product.get(key) for key in ("title", "category"))
    return list(dict.fromkeys(" ".join(t.split())[:240] for t in terms if isinstance(t, str) and t.strip()))[
        :5
    ]


def words(text):
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


class TaxonomyLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.current = [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.current = [attrs.get("href", ""), []]
        if tag == "img" and self.current:
            self.current[1].append(attrs.get("alt", ""))

    def handle_data(self, data):
        if self.current:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            self.rows.append((self.current[0], " ".join(" ".join(self.current[1]).split())))
            self.current = None


async def category_pages(reader, product, *, root="https://www.oreillyauto.com", limit=3):
    """Follow actual taxonomy links; matching a category is never fitment evidence."""
    target = words(product.get("category")) or words(product.get("title"))
    if not target:
        return []
    url, seen, pages = root + "/shop/b", set(), []
    for _ in range(limit):
        if url in seen:
            break
        seen.add(url)
        html = await reader.read(url, headers={"Accept": "text/html"})
        if not html:
            break
        pages.append((url, html))
        parser = TaxonomyLinks()
        parser.feed(html)
        ranked = []
        for href, label in parser.rows:
            candidate = urljoin(root, href)
            parsed = urlsplit(candidate)
            tokens = words(label)
            if (
                parsed.scheme != "https"
                or parsed.netloc != urlsplit(root).netloc
                or not parsed.path.startswith("/shop/b/")
                or parsed.query
                or parsed.fragment
                or ".." in parsed.path.split("/")
                or candidate in seen
            ):
                continue
            if tokens and tokens <= target:
                ranked.append((len(tokens), candidate))
        if not ranked:
            break
        best = max(score for score, _ in ranked)
        candidates = {link for score, link in ranked if score == best}
        if len(candidates) != 1:
            break
        url = candidates.pop()
    return pages
