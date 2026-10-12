from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.comparison import comparable_prices
from gaswise.main import create_app
from gaswise.providers.pricing.aggregation import MultiSourceProvider
from gaswise.services.pricing.search import SearchService
from tests.support.comparison import (
    NOW as NOW,
)
from tests.support.comparison import (
    ORIGIN as ORIGIN,
)
from tests.support.comparison import (
    Prices as Prices,
)
from tests.support.comparison import (
    quote as quote,
)
from tests.support.comparison import (
    select as select,
)


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


def test_credit_price_is_excluded_for_explicit_cash_request():
    selected, excluded, _ = select([quote()], payment_type="cash")
    assert selected == [] and excluded == 1


def test_unknown_payment_requires_explicit_opt_in():
    unknown = quote().model_copy(update={"payment_type": "unknown"})
    selected, excluded, _ = select([unknown])
    assert selected == [] and excluded == 1
    selected, excluded, _ = select([unknown], allow_unknown_payment=True)
    assert len(selected) == 1 and excluded == 0


def test_unknown_payment_is_not_corroboration_for_verified_credit():
    unknown = quote().model_copy(update={"payment_type": "unknown"})
    selected, _, warnings = select(
        [unknown, quote("gasbuddy_web", "gb1", canonical_id="google_places:a")],
        allow_unknown_payment=True,
    )
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


def test_any_source_reporting_closed_excludes_the_whole_station():
    open_maps = quote(canonical_id="google_places:a", open_now=True)
    closed_waze = quote("waze", "wz1", "5.00", canonical_id="google_places:a", open_now=False)
    selected, excluded, _ = select([open_maps, closed_waze])
    assert selected == [] and excluded == 2
    _, _, kept = select([open_maps, closed_waze], opening_policy="ignore")
    assert not any("Opening status" in w for w in kept)
    assert len(select([open_maps, closed_waze], opening_policy="ignore")[0]) == 1


def test_closed_business_status_excludes_even_with_open_weekly_hours():
    record = quote(open_now=True, business_status="permanently_closed")
    assert select([record])[0] == []


def test_unknown_hours_are_kept_with_warning_unless_open_is_required():
    selected, _, warnings = select([quote()])
    assert len(selected) == 1
    assert any("Opening status is unknown for 1 eligible stations" in w for w in warnings)
    selected, excluded, _ = select([quote()], opening_policy="require_open")
    assert selected == [] and excluded == 1
    assert len(select([quote(open_now=True)], opening_policy="require_open")[0]) == 1


def test_mislocated_crosswalk_record_cannot_close_the_station():
    far = Point(lat=ORIGIN.lat + 0.01, lng=ORIGIN.lng)
    mislocated = quote("waze", "wz1", canonical_id="google_places:a", open_now=False).model_copy(
        update={"location": far}
    )
    selected, _, _ = select([quote(canonical_id="google_places:a", open_now=True), mislocated])
    assert len(selected) == 1
    assert selected[0].evidence[0].exclusion_reason is None
    assert selected[0].evidence[1].exclusion_reason == "station_mapping_location_mismatch"


def test_all_payment_keeps_actual_basis_and_does_not_claim_cross_payment_agreement():
    credit = quote("gasbuddy_web", "gb1", "6.00", canonical_id="google_places:a")
    cash = credit.model_copy(update={"payment_type": "cash", "price_per_gallon": Decimal("5.50")})
    selected, excluded, _ = select([credit, cash], payment_type="cash_or_credit")
    assert excluded == 0
    assert selected[0].station.payment_type == "cash"
    assert selected[0].station.price_per_gallon == Decimal("5.50")
    assert len(selected[0].quotes) == 1
    assert selected[0].evidence[0].comparison_exclusion_reason == "purchase_conditions_not_comparable"
    unknown = credit.model_copy(update={"payment_type": "unknown"})
    assert select([unknown], payment_type="cash_or_credit")[0] == []


def test_station_metadata_can_merge_without_promoting_payment_amenity():
    unknown = quote("waze", "venue1", "5.00", canonical_id="google_places:a").model_copy(update={"payment_type": "unknown", "details": {"phone": "+1 555 0100", "accepts_credit_cards": True}, "rating": 4.2, "review_count": 315, "rating_source": "Google via Waze"})
    credit = quote("gasbuddy_web", "gb1", "6.00", canonical_id="google_places:a")
    selected, _, _ = select([unknown, credit])
    assert selected[0].station.payment_type == "credit"
    assert selected[0].station.price_per_gallon == Decimal("6.00")
    assert selected[0].station.rating == 4.2
    assert selected[0].station.details["phone"] == "+1 555 0100"
    assert not selected[0].evidence[0].eligible
