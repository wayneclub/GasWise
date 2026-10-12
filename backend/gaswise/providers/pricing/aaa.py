"""Read AAA's public daily averages without treating them as station quotes."""

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

import httpx
from pydantic import BaseModel

from gaswise.domain.ports import ProviderError

STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
FUELS = ("regular", "mid_grade", "premium", "diesel")
PERIODS = dict(
    zip(
        ("Current Avg.", "Yesterday Avg.", "Week Ago Avg.", "Month Ago Avg.", "Year Ago Avg."),
        ("current", "yesterday", "week_ago", "month_ago", "year_ago"),
        strict=True,
    )
)


class RegionAverage(BaseModel):
    name: str
    level: str
    prices: dict[str, dict[str, Decimal | None]]


class AAASnapshot(BaseModel):
    source: str = "aaa"
    source_url: str
    state: str
    price_as_of: date
    retrieved_at: datetime
    update_frequency: str = "daily"
    currency: str = "USD"
    volume_unit: str = "US_gallon"
    regions: list[RegionAverage]
    county_status: str


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading = ""
        self.capture = None
        self.parts = []
        self.rows = []
        self.row = []
        self.tables = []
        self.in_table = False

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h3", "td", "th"):
            self.capture = tag
            self.parts = []
        if tag == "table":
            self.in_table = True
            self.rows = []
        if tag == "tr":
            self.row = []

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.capture:
            value = " ".join("".join(self.parts).split())
            if tag in ("h1", "h3"):
                self.heading = value.replace(" average gas prices", "")
            else:
                self.row.append(value)
            self.capture = None
        if tag == "tr" and self.in_table:
            self.rows.append(self.row)
        if tag == "table":
            self.tables.append((self.heading, self.rows))
            self.in_table = False


def money(value):
    value = value.strip().removeprefix("$")
    if not value or value in ("-", "--", "N/A"):
        return None
    result = Decimal(value)
    if not result.is_finite() or result <= 0:
        raise ValueError("invalid price")
    return result


def parse_page(html, state):
    match = re.search(r"Price as of\s*(\d{1,2}/\d{1,2}/\d{2,4})", html)
    if not match:
        raise ProviderError("aaa_missing_price_date")
    fmt = "%m/%d/%Y" if len(match[1].split("/")[-1]) == 4 else "%m/%d/%y"
    published = datetime.strptime(match[1], fmt).date()
    parser = Tables()
    parser.feed(html)
    regions = []
    for name, rows in parser.tables:
        prices = {}
        for row in rows:
            if row and row[0] in PERIODS:
                if len(row) != 5:
                    raise ProviderError("aaa_invalid_price_table")
                prices[PERIODS[row[0]]] = dict(zip(FUELS, map(money, row[1:]), strict=True))
        if prices:
            if not name or set(prices) != set(PERIODS.values()):
                raise ProviderError("aaa_incomplete_price_table")
            regions.append(RegionAverage(name=name, level="state" if not regions else "metro", prices=prices))
    if not regions:
        raise ProviderError("aaa_missing_price_tables")
    return published, regions


class AAAProvider:
    def __init__(self, client):
        self.client = client

    async def averages(self, state):
        url = f"https://gasprices.aaa.com/?state={state}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            published, regions = parse_page(response.text, state)
            county_status = "unavailable"
            # Only follow the observed same-origin map endpoint; never execute its JavaScript.
            map_id = re.search(r"premiumhtml5map_js_data=true(?:&amp;|&#038;|&)map_id=(\d+)", response.text)
            if map_id:
                try:
                    county_response = await self.client.get(
                        "https://gasprices.aaa.com/index.php",
                        params={"premiumhtml5map_js_data": "true", "map_id": map_id[1]},
                    )
                    county_response.raise_for_status()
                    start = re.search(r"map_data\s*:\s*", county_response.text)
                    if start:
                        counties, _ = json.JSONDecoder().raw_decode(county_response.text[start.end() :])
                        for county in counties.values():
                            regions.append(
                                RegionAverage(
                                    name=county["name"],
                                    level="county",
                                    prices={"current": {"regular": money(county["comment"])}},
                                )
                            )
                        county_status = "available"
                except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
                    county_status = "unavailable"
            return AAASnapshot(
                source_url=url,
                state=state,
                price_as_of=published,
                retrieved_at=datetime.now(UTC),
                regions=regions,
                county_status=county_status,
            )
        except httpx.HTTPError as error:
            raise ProviderError("aaa_upstream_unavailable") from error
        except (ValueError, InvalidOperation) as error:
            raise ProviderError("aaa_invalid_response") from error
