from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gaswise.contracts.common import Point, Route, Station
from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.comparison import select_prices

NOW = datetime.now(UTC)

ORIGIN = Point(lat=34.03938, lng=-118.2663)


def quote(source="google_places", station_id="a", price="6.00", age=5, **kwargs):
    return Station(
        id=station_id,
        name="Station",
        location=ORIGIN,
        fuel_type="premium",
        price_per_gallon=Decimal(price),
        fetched_at=NOW,
        price_updated_at=NOW - timedelta(minutes=age),
        source=source,
        payment_type="credit",
        **kwargs,
    )


def select(records, **kwargs):
    return select_prices(records, Search(origin=ORIGIN, **kwargs), NOW)


class Prices:
    def __init__(self, records=None, error=False):
        self.records, self.error = records or [], error

    async def stations(self, _):
        if self.error:
            raise ProviderError("upstream_unavailable")
        return self.records

    async def route(self, origin, destination, via=None):
        return Route(distance_meters=0, duration_seconds=0, source="fixture")
