from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gaswise.comparison import comparable_prices, select_prices
from gaswise.main import create_app
from gaswise.models import Point, Route, Search, Station
from gaswise.providers.base import ProviderError
from gaswise.providers.multi import MultiSourceProvider
from gaswise.service import SearchService
from gaswise.settings import Settings

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


def test_preferred_gasbuddy_is_selected_when_equally_fresh():
    selected, _, _ = select([quote(), quote("gasbuddy_web", "gb1", "5.99", canonical_id="google_places:a")])
    assert len(selected) == 1
    assert selected[0].station.source == "gasbuddy_web"
    assert comparable_prices(selected[0])[3:] == ("consistent", "corroborated", 2)


def test_old_preferred_price_does_not_override_recent_quote():
    selected, _, _ = select(
        [quote(), quote("gasbuddy_web", "gb1", "5.00", age=180, canonical_id="google_places:a")]
    )
    assert selected[0].station.source == "google_places"
    assert comparable_prices(selected[0])[3] == "conflicting"


def test_cash_quote_is_ineligible_for_credit_request():
    cash = quote("gasbuddy_web", "gb1", "4.00", canonical_id="google_places:a").model_copy(
        update={"payment_type": "cash"}
    )
    selected, excluded, _ = select([quote(), cash])
    assert excluded == 1
    assert selected[0].station.source == "google_places"
    assert selected[0].evidence[1].exclusion_reason == "payment_type_mismatch"


def test_credit_price_is_payable_by_cash_user():
    selected, excluded, _ = select([quote()], payment_type="cash")
    assert len(selected) == 1 and excluded == 0


def test_unknown_payment_is_not_corroboration_for_verified_credit():
    unknown = quote().model_copy(update={"payment_type": "unknown"})
    selected, _, warnings = select([unknown, quote("gasbuddy_web", "gb1", canonical_id="google_places:a")])
    assert comparable_prices(selected[0])[-1] == 1
    assert warnings


def test_same_id_from_different_sources_does_not_merge_without_crosswalk():
    selected, _, _ = select([quote(), quote("gasbuddy_web")])
    assert len(selected) == 2


def test_same_brand_and_nearby_location_does_not_merge_without_crosswalk():
    selected, _, _ = select([quote(), quote("gasbuddy_web", "different")])
    assert len(selected) == 2


def test_incorrect_crosswalk_is_excluded_by_location():
    wrong = quote("gasbuddy_web", "gb1", canonical_id="google_places:a").model_copy(
        update={"location": Point(lat=34.04, lng=-118.27)}
    )
    selected, excluded, _ = select([quote(), wrong])
    assert excluded == 1
    assert selected[0].evidence[1].exclusion_reason == "station_mapping_location_mismatch"


def test_stale_price_and_future_price_are_excluded():
    selected, excluded, _ = select([quote(age=2000), quote("gasbuddy_web", age=-10)])
    assert selected == [] and excluded == 2


def test_duplicate_source_reports_do_not_create_consensus():
    selected, _, _ = select([quote(), quote(price="6.01", age=6)])
    assert comparable_prices(selected[0])[-1] == 1
    assert comparable_prices(selected[0])[3] == "single_source"


def test_verified_91_filters_unverified_google_and_keeps_verified_quote():
    selected, excluded, _ = select(
        [quote(), quote("gasbuddy", "gb1", octane=91, canonical_id="google_places:a")], required_octane=91
    )
    assert selected[0].station.source == "gasbuddy" and excluded == 1


class Prices:
    def __init__(self, records=None, error=False):
        self.records, self.error = records or [], error

    async def stations(self, _):
        if self.error:
            raise ProviderError("upstream_unavailable")
        return self.records

    async def route(self, origin, destination, via=None):
        return Route(distance_meters=0, duration_seconds=0, source="fixture")


async def test_source_failure_does_not_erase_successful_source():
    router = Prices([quote()])
    provider = MultiSourceProvider(router, {"google_places": router, "gasbuddy_web": Prices(error=True)})
    result = await SearchService(provider, "google").search(Search(origin=ORIGIN))
    assert result.results[0].station.source == "google_places"
    assert result.source_statuses[1].status == "unavailable"
    assert result.decision.status == "single_source"


async def test_all_price_source_failures_raise():
    provider = MultiSourceProvider(Prices(), {"one": Prices(error=True), "two": Prices(error=True)})
    with pytest.raises(ProviderError, match="all_price_sources_unavailable"):
        await provider.snapshot(Search(origin=ORIGIN))


async def test_best_value_does_not_rank_by_optimistic_conflicting_price():
    records = [
        quote(station_id="a", price="5"),
        quote("gasbuddy_web", "gb1", "7", canonical_id="google_places:a"),
        quote(station_id="b", price="6"),
        quote("gasbuddy_web", "gb2", "6", canonical_id="google_places:b"),
    ]
    provider = Prices(records)
    query = Search(origin=ORIGIN, strategy="best_value", preferred_sources=["google_places"])
    result = await SearchService(provider, "google").search(query)
    assert result.results[0].station.id == "b"
    assert result.results[1].price_comparison.comparable_cost_max == Decimal("70.00")
    assert result.decision.status == "uncertain"


async def test_winner_remains_cheaper_across_comparable_ranges():
    records = [
        quote(station_id="a", price="5"),
        quote("gasbuddy_web", "gb1", "5.02", canonical_id="google_places:a"),
        quote(station_id="b", price="6"),
        quote("gasbuddy_web", "gb2", "6.02", canonical_id="google_places:b"),
    ]
    result = await SearchService(Prices(records), "google").search(Search(origin=ORIGIN))
    assert result.decision.status == "robust"


def test_gasbuddy_endpoint_disabled_is_explicit():
    with TestClient(create_app(Settings(), Prices())) as api:
        assert (
            api.post(
                "/v1/sources/gasbuddy/prices", json={"origin": ORIGIN.model_dump(), "postal_code": "90015"}
            ).status_code
            == 503
        )


def test_website_source_requires_token():
    with pytest.raises(ValueError):
        Settings(gasbuddy_web_enabled=True)


def test_old_corroborating_quote_does_not_claim_fresh_consensus():
    selected, _, _ = select([quote(), quote("gasbuddy_web", "gb1", age=180, canonical_id="google_places:a")])
    assert comparable_prices(selected[0], NOW)[4] == "limited"
