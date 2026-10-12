import gzip
import json

import pytest

from gaswise.providers.parts.oreilly_catalog import OReillyCatalog, candidates, unpack

ROOT = "https://www.oreillyauto.com"


def xml(urls):
    return (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join("<url><loc>" + u + "</loc></url>" for u in urls)
        + "</urlset>"
    )


async def test_public_url_discovery_verifies_brand_and_caches_documents():
    class Reader:
        downloads = 0

        async def read(self, url, **kwargs):
            if url.endswith("/sitemap.xml"):
                return xml([ROOT + "/sitemap1.xml.gz"])
            assert url.endswith("/pcp/compare-items")
            return json.dumps(
                [
                    {"lineCode": "KAN", "itemNumber": "HP7040", "productName": "K&N Engineering Oil Filter"},
                    {"lineCode": "STD", "itemNumber": "HP7040", "productName": "Standard Ignition Terminal"},
                ]
            )

        async def read_sitemap(self, url):
            self.downloads += 1
            return gzip.compress(
                xml(
                    [
                        ROOT + "/detail/c/k-n-engineering/filter/kan0/hp7040",
                        ROOT + "/detail/c/standard-ignition/terminal/std0/hp7040",
                    ]
                ).encode()
            )

    reader, catalog = Reader(), OReillyCatalog()
    for _ in range(2):
        result = await catalog.discover(reader, {"brand": "K&N Engineering", "identifiers": ["HP7040"]})
        assert result["part"] == {"lineCode": "KAN", "itemNumber": "HP7040"}
    assert reader.downloads == 1
    assert await catalog.discover(reader, {"brand": "Knox", "identifiers": ["HP7040"]}) is None


def test_catalog_rejects_offsite_tracking_and_similar_part_numbers():
    urls = [
        "https://evil.test/detail/c/wix/oil/wix0/57060",
        ROOT + "/detail/c/wix/oil/wix0/570600",
        ROOT + "/detail/c/wix/oil/wix0/57060?q=tracking",
        ROOT + "/detail/c/wix/oil/wix0/57060",
    ]
    result = candidates([xml(urls).encode()], {"brand": "WIX", "identifiers": ["57060"]})
    assert result == {("WIX", "57060"): urls[-1]}


def test_gzip_expansion_is_bounded():
    with pytest.raises(ValueError, match="sitemap_expansion_limit"):
        unpack(gzip.compress(b"x" * 24_000_001))
