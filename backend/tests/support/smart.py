from datetime import UTC, datetime

from gaswise.contracts.common import Point, Station
from gaswise.contracts.sources import (
    GasBuddyPrices,
    GasBuddyQuote,
    GasBuddySearch,
    MapsWebPrices,
    MapsWebStation,
)
from tests.support.service import FixtureProvider


class CountingProvider(FixtureProvider):
    searches = 0
    routes = 0

    async def stations(self, query, *, all_fuels=False):
        self.searches += 1
        return await super().stations(query)

    async def route(self, origin, destination, via=None):
        self.routes += 1
        return await super().route(origin, destination, via)


class RawGasBuddy:
    calls = 0

    async def prices(self, query):
        self.calls += 1
        # The raw contract supports GPS. Passing Search here rejected GPS-only
        # queries even though the raw GasBuddy API supported them.
        assert isinstance(query, GasBuddySearch)
        now = datetime.now(UTC)
        return GasBuddyPrices(
            fetched_at=now,
            partial=False,
            warnings=[],
            prices=[
                GasBuddyQuote(
                    id="gb1",
                    name="Shell",
                    address="1516 S Main St, Los Angeles, CA 90015",
                    street="1516 S Main St",
                    city="Los Angeles",
                    region="CA",
                    postal_code="90015",
                    price_per_gallon="5.99",
                    fuel_type="premium",
                    payment_type="credit",
                    price_updated_at=now,
                    fetched_at=now,
                    report_kind="community",
                    source_url="https://www.gasbuddy.com/station/gb1",
                )
            ],
        )


def inventory():
    # Matching place deliberately has no Google fuel price: location must still work.
    return {
        "places": [
            {
                "id": "gp1",
                "displayName": {"text": "Shell"},
                "location": {"latitude": 34, "longitude": -118},
                "addressComponents": [
                    {"types": ["country"], "shortText": "US"},
                    {"types": ["street_number"], "longText": "1516"},
                    {"types": ["route"], "shortText": "S Main St"},
                    {"types": ["locality"], "longText": "Los Angeles"},
                    {"types": ["administrative_area_level_1"], "shortText": "CA"},
                    {"types": ["postal_code"], "longText": "90015"},
                ],
            }
        ]
    }


class MapsInventory:
    calls = 0

    async def prices(self, query):
        self.calls += 1
        now = datetime.now(UTC)
        return MapsWebPrices(
            inventory=[
                MapsWebStation(
                    place_id="gp1",
                    name="Shell",
                    location=Point(lat=34, lng=-118),
                    address="1516 S Main St, Los Angeles, CA 90015",
                    distance_meters=0,
                    available_fuel_types=["premium"],
                )
            ],
            stations=[
                Station(
                    id="google_maps_web:gp1",
                    canonical_id="google_places:gp1",
                    name="Shell",
                    location=Point(lat=34, lng=-118),
                    source="google_maps_web",
                    fuel_type="premium",
                    price_per_gallon="6.10",
                    payment_type="unknown",
                    price_updated_at=now,
                    fetched_at=now,
                    details={"location_source": "google_maps_web"},
                )
            ],
            warnings=[],
        )


class WazeQuotes:
    calls = 0

    async def stations(self, query, *, all_fuels=False):
        self.calls += 1
        now = datetime.now(UTC)
        return [
            Station(
                id="wz1",
                name="Shell",
                location=Point(lat=34.00001, lng=-118),
                address="1516 S Main St Los Angeles CA 90015",
                source="waze",
                fuel_type="premium",
                price_per_gallon="5.90",
                payment_type="unknown",
                price_updated_at=now,
                fetched_at=now,
            )
        ]
