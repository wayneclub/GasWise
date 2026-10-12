from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.contracts.search import RankOptions
from gaswise.contracts.smart import SmartRerank, SmartSearch
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.top_tier import match_top_tier, us_brand_index
from gaswise.main import create_app
from gaswise.providers.pricing.demo import DemoProvider
from gaswise.providers.quality.top_tier import SOURCE_URL, TopTierProvider, parse_brand_page
from gaswise.services.pricing.smart import SmartService

US_FILLER = "".join(f"<tr><td>Brand {i}</td><td>USA</td></tr>" for i in range(30))


def page(rows: str, modified="2026-08-27T13:31:16-04:00") -> str:
    # Shape observed on the public page on 2026-10-11: one Brand / Country table.
    return (
        f'<meta property="article:modified_time" content="{modified}" />'
        "<table><thead><tr><th>Brand</th><th>Country</th></tr></thead><tbody>"
        f"{rows}{US_FILLER}</tbody></table>"
    )


ROWS = (
    "<tr><td>Chevron</td><td>USA</td></tr>"
    "<tr><td>Costco / Kirkland Signature</td><td>USA</td></tr>"
    "<tr><td>Costco / Kirkland Signature</td><td>Japan</td></tr>"
    "<tr><td>Express Mart</td><td>USA</td></tr>"
    "<tr><td>Phillips 66</td><td>USA</td></tr>"
    "<tr><td>Puma Energy</td><td>Argentina</td></tr>"
    "<tr><td>Shell</td><td>USA</td></tr>"
)


def provider(handler, cache_file=None):
    return TopTierProvider(httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache_file, 168)


def test_parser_merges_countries_and_reads_modified_time():
    data = parse_brand_page(page(ROWS), datetime.now(UTC))
    costco = next(b for b in data.brands if b.name.startswith("Costco"))
    assert costco.countries == ["Japan", "USA"]
    assert data.page_modified_at.isoformat() == "2026-08-27T13:31:16-04:00"
    assert data.origin == "live" and data.source_url == SOURCE_URL


def test_parser_refuses_a_changed_or_truncated_page():
    with pytest.raises(ProviderError, match="table_not_found"):
        parse_brand_page("<table><tr><th>Name</th></tr></table>", datetime.now(UTC))
    short = "<table><tr><th>Brand</th><th>Country</th></tr><tr><td>Shell</td><td>USA</td></tr></table>"
    with pytest.raises(ProviderError, match="incomplete"):
        parse_brand_page(short, datetime.now(UTC))


@pytest.mark.parametrize(
    "name,hint,brand",
    [
        ("Chevron ExtraMile Los Angeles", None, "Chevron"),
        ("Chevron/ Extra Mile", None, "Chevron"),
        ("Kirkland Signature Gas", None, "Costco / Kirkland Signature"),
        ("Costco Gasoline", None, "Costco / Kirkland Signature"),
        ("Phillips 66", None, "Phillips 66"),
        ("Gas station", "Shell", "Shell"),
        ("Shellbrook Fuel", None, None),
        ("Express Mart", None, "Express Mart"),
        ("Express Mart Fuel", None, None),
        ("Puma Energy", None, None),
        ("Speedway", None, None),
    ],
)
def test_brand_matching_rules(name, hint, brand):
    index = us_brand_index(parse_brand_page(page(ROWS), datetime.now(UTC)).brands)
    assert match_top_tier(name, hint, index) == brand


async def test_refresh_updates_and_caches_then_cold_start_uses_cache(tmp_path):
    cache = tmp_path / "top-tier.json"
    source = provider(lambda request: httpx.Response(200, text=page(ROWS)), cache)
    assert source.current().origin == "bundled" and source.is_stale()
    async with source.client:
        await source.refresh()
    assert source.current().origin == "live" and cache.exists()
    assert not source.is_stale()
    reloaded = provider(lambda request: httpx.Response(500), cache)
    assert reloaded.current().origin == "cache"
    assert reloaded.is_stale(datetime.now(UTC) + timedelta(days=8))


async def test_failed_or_suspicious_refresh_keeps_the_previous_list(tmp_path):
    source = provider(lambda request: httpx.Response(503))
    before = source.current()
    async with source.client:
        with pytest.raises(ProviderError, match="unavailable"):
            await source.refresh()
    assert source.current() is before
    broken = provider(lambda request: httpx.Response(200, text="<html>maintenance</html>"))
    async with broken.client:
        with pytest.raises(ProviderError):
            await broken.refresh()
    assert broken.current().origin == "bundled" and len(broken.index) > 50


async def test_bundled_snapshot_tags_demo_stations_and_filter_reranks_without_calls():
    top_tier = provider(lambda request: httpx.Response(500))
    service = SmartService(b"test", "demo", demo=DemoProvider(), top_tier=top_tier)
    result = await service.search(
        SmartSearch(origin=Point(lat=34, lng=-118), radius_meters=15000, calculate_routes=True)
    )
    tags = {s.name: s.top_tier_brand for s in result.snapshot.stations}
    assert tags == {"Chevron": "Chevron", "Shell": "Shell", "Arco": "ARCO", "Gulf": None}
    only = await service.rerank(
        SmartRerank(
            snapshot=result.snapshot, signature=result.signature, options=RankOptions(top_tier_only=True)
        )
    )
    assert "Gulf" not in {row.station.name for row in only.ranking.results}
    assert only.ranking.results and all(row.station.top_tier_brand for row in only.ranking.results)
    assert not any(only.upstream_calls.values())


def test_endpoint_serves_current_list_and_capabilities():
    with TestClient(create_app(Settings())) as client:
        body = client.get("/v1/quality/top-tier").json()
        assert body["origin"] == "bundled" and body["program"] == "TOP TIER Detergent Gasoline"
        assert sum("USA" in brand["countries"] for brand in body["brands"]) >= 30
        assert client.get("/v1/capabilities").json()["top_tier_list_origin"] == "bundled"


class OnlyShell:
    """Brand index stub: Shell is licensed, the other demo brands are not."""

    index = us_brand_index(
        parse_brand_page(page("<tr><td>Shell</td><td>USA</td></tr>"), datetime.now(UTC)).brands
    )


async def test_top_tier_preference_only_wins_within_the_cost_margin():
    service = SmartService(b"test", "demo", demo=DemoProvider(), top_tier=OnlyShell())
    first = await service.search(SmartSearch(origin=Point(lat=34, lng=-118), calculate_routes=True))

    async def best(**options):
        result = await service.rerank(
            SmartRerank(snapshot=first.snapshot, signature=first.signature, options=RankOptions(**options))
        )
        return result.ranking.recommendations

    # Default 5 cents per gallon: Shell costs about $1.19 more than Arco for 10 gal, so cost wins.
    default = await best()
    assert default["best_value"].station.name == "Arco"
    assert default["best_value"].top_tier_preferred_over is None
    # A wider margin lets the licensed brand lead, and the response states the premium.
    wide = await best(top_tier_margin_per_gallon="0.20")
    assert wide["best_value"].station.name == "Shell"
    note = wide["best_value"].top_tier_preferred_over
    assert note.station_name == "Arco" and 0 < note.extra_cost <= note.margin == 2
    # Lowest cost and quickest stay pure; the preference can be switched off.
    assert wide["cheapest_overall"].station.name == "Arco"
    off = await best(top_tier_margin_per_gallon="0.20", prefer_top_tier=False)
    assert off["best_value"].station.name == "Arco"
