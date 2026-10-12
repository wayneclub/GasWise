from decimal import Decimal

import pytest
from pydantic import ValidationError

from gaswise.contracts.common import Route
from gaswise.contracts.search import Search
from gaswise.services.pricing.search import SearchService
from tests.support.comparison import ORIGIN, Prices, quote, select


class DetourPrices(Prices):
    async def route(self, origin, destination, via=None):
        return Route(distance_meters=1609.344 if via else 0, duration_seconds=60 if via else 0, source="fixture")


@pytest.mark.parametrize("payment", ["credit", "cash", "unknown"])
async def test_reward_only_applies_to_card_purchase_and_preserves_raw_quote(payment):
    station = quote(price="5.00").model_copy(update={"payment_type": payment})
    query = Search(origin=ORIGIN, fuel_type="premium", mpg="10", gallons="10", payment_type="cash" if payment == "cash" else "credit", allow_unknown_payment=True, unknown_payment_credit_markup="0.20", credit_cashback_percent="5")
    row = (await SearchService(DetourPrices([station]), "prices_only").search(query)).results[0]
    assert row.station.price_per_gallon == Decimal("5.00")
    assert row.station.payment_type == payment
    gross = Decimal("52") if payment == "unknown" else Decimal("50")
    reward = Decimal("0") if payment == "cash" else gross * Decimal("0.05")
    assert row.purchase_cost == gross
    assert row.credit_cashback_amount == reward
    assert row.net_purchase_cost == gross - reward
    # Card rewards apply to this purchase, not the fuel burned driving there.
    assert row.detour_fuel_cost == gross / Decimal("100")
    assert row.actual_fuel_cost == gross - reward + row.detour_fuel_cost
    assert row.price_comparison.comparable_cost_min == row.actual_fuel_cost


def test_all_payment_search_can_choose_card_after_rewards():
    cash = quote(price="5.00").model_copy(update={"payment_type": "cash"})
    credit = quote(price="5.10")
    assert select([cash, credit], payment_type="cash_or_credit")[0][0].station.payment_type == "cash"
    selected = select([cash, credit], payment_type="cash_or_credit", credit_cashback_percent="5")[0][0]
    assert selected.station.payment_type == "credit"
    assert selected.station.price_per_gallon == Decimal("5.10")


@pytest.mark.parametrize("value", ["-1", "101", "NaN", "Infinity"])
def test_reward_percentage_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        Search(origin=ORIGIN, credit_cashback_percent=value)
