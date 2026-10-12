"""TOP TIER licensed-brand list from the program's public brand table.

The list changes a few times a year, so it is refreshed on a schedule and never per search.
A bundled snapshot keeps matching available offline; a failed or suspicious refresh keeps
the last good list instead of clearing it.
"""

import asyncio
import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import httpx

from gaswise.contracts.quality import TopTierBrand, TopTierList
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.top_tier import us_brand_index

SOURCE_URL = "https://www.toptiergas.com/gasoline-brands/"
BUNDLED = Path(__file__).with_name("top_tier_brands.json")
# The table listed 78 US brands in 2026; far fewer means the page changed, not the program.
MIN_US_BRANDS = 30
log = logging.getLogger(__name__)


class _BrandTable(HTMLParser):
    """Rows of the first table whose header row is Brand / Country."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.depth = 0
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.tables.append([])
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "table":
            self.depth = max(0, self.depth - 1)
        elif self.depth == 1 and tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif self.depth == 1 and tag == "tr" and self.row is not None:
            self.tables[-1].append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def parse_brand_page(page: str, fetched_at: datetime) -> TopTierList:
    parser = _BrandTable()
    parser.feed(page)
    for rows in parser.tables:
        if not rows or [cell.lower() for cell in rows[0][:2]] != ["brand", "country"]:
            continue
        brands: dict[str, set[str]] = {}
        for row in rows[1:]:
            if len(row) < 2 or not row[0]:
                continue
            countries = {part.strip() for part in re.split(r"[,/;]", row[1]) if part.strip()}
            brands.setdefault(row[0], set()).update(countries)
        result = TopTierList(
            source_url=SOURCE_URL,
            page_modified_at=_modified(page),
            fetched_at=fetched_at,
            origin="live",
            brands=[TopTierBrand(name=name, countries=sorted(c)) for name, c in sorted(brands.items())],
        )
        if sum("USA" in brand.countries for brand in result.brands) < MIN_US_BRANDS:
            raise ProviderError("top_tier_brand_table_incomplete")
        return result
    raise ProviderError("top_tier_brand_table_not_found")


def _modified(page: str) -> datetime | None:
    match = re.search(r'article:modified_time"\s+content="([^"]+)"', page)
    try:
        return datetime.fromisoformat(match[1]) if match else None
    except ValueError:
        return None


class TopTierProvider:
    def __init__(self, client: httpx.AsyncClient, cache_file: Path | None, refresh_hours: int):
        self.client = client
        self.cache_file = cache_file
        self.refresh_interval = timedelta(hours=refresh_hours)
        self.data = self._load()
        self.index = us_brand_index(self.data.brands)

    def _load(self) -> TopTierList:
        if self.cache_file is not None:
            try:
                return TopTierList.model_validate_json(self.cache_file.read_text()).model_copy(
                    update={"origin": "cache"}
                )
            except (OSError, ValueError):
                pass
        return TopTierList.model_validate_json(BUNDLED.read_text()).model_copy(update={"origin": "bundled"})

    def current(self) -> TopTierList:
        return self.data

    def is_stale(self, now: datetime | None = None) -> bool:
        return (
            self.data.origin == "bundled"
            or (now or datetime.now(UTC)) - self.data.fetched_at >= self.refresh_interval
        )

    async def refresh(self) -> TopTierList:
        try:
            response = await self.client.get(
                SOURCE_URL,
                headers={"User-Agent": "GasWise/0.1 (+brand list refresh)", "Accept": "text/html"},
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise ProviderError("top_tier_unavailable") from None
        if response.status_code != 200:
            raise ProviderError("top_tier_unavailable")
        fresh = parse_brand_page(response.text, datetime.now(UTC))
        self.data, self.index = fresh, us_brand_index(fresh.brands)
        self._save(fresh)
        return fresh

    def _save(self, data: TopTierList):
        if self.cache_file is None:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_file.with_suffix(".tmp")
            temporary.write_text(data.model_dump_json(indent=2))
            os.replace(temporary, self.cache_file)
        except OSError:
            log.warning("TOP TIER cache could not be written; keeping the list in memory")

    async def run(self):
        """Scheduled refresh: check on start, then once per interval. Failures keep the last good list."""
        while True:
            if self.is_stale():
                try:
                    data = await self.refresh()
                    log.info("TOP TIER list refreshed: %d brands", len(data.brands))
                except ProviderError as error:
                    log.warning("TOP TIER refresh failed (%s); keeping %s list", error, self.data.origin)
            await asyncio.sleep(min(self.refresh_interval.total_seconds(), 6 * 3600))


def snapshot_json(data: TopTierList) -> str:
    """Bundled-file form, used by the maintenance script that updates the shipped snapshot."""
    return json.dumps(json.loads(data.model_dump_json()), indent=2, ensure_ascii=False) + "\n"
