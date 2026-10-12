from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from gaswise.contracts.sources import GasBuddySearch, gasbuddy_variables
from gaswise.providers.gasbuddy.web import GasBuddyWebProvider
from tests.support.gasbuddy_web import transport


@pytest.mark.parametrize("term", ["Los Angeles, CA", "90015"])
def test_text_location_without_gps(term):
    query = GasBuddySearch(search=term, brand_id=8)
    assert gasbuddy_variables(query, 3)["search"] == term
    assert gasbuddy_variables(query, 3)["brandId"] == 8


@pytest.mark.parametrize("payload", [{}, {"search": "  "}, {"search": "LA", "postal_code": "90015"}])
def test_invalid_location(payload):
    with pytest.raises(ValidationError):
        GasBuddySearch(**payload)


async def test_cash_or_credit_reports_actual_lower_payment():
    async with httpx.AsyncClient(transport=transport(timestamp=datetime.now(UTC).isoformat())) as client:
        result = await GasBuddyWebProvider(client).prices(
            GasBuddySearch(postal_code="90015", payment_type="cash_or_credit")
        )
    assert result.prices[0].payment_type == "cash"
    assert str(result.prices[0].price_per_gallon) == "6.79"


@pytest.mark.parametrize("posted", [None, (datetime.now(UTC) - timedelta(hours=2)).isoformat()])
async def test_age_filter_excludes_unknown_and_old_reports(posted):
    async with httpx.AsyncClient(transport=transport(timestamp=posted)) as client:
        result = await GasBuddyWebProvider(client).prices(
            GasBuddySearch(postal_code="90015", max_price_age_minutes=60)
        )
    assert result.prices == []


async def test_station_after_limit_is_considered_and_costco_membership_preserved():
    async def snapshot(query, url, fuel):
        state = {}
        results = []
        for i, name in enumerate(["Shell", "Chevron", "Costco"]):
            state[f"Station:{i}"] = {
                "name": name,
                "priceUnit": "dollars_per_gallon",
                "address": {
                    "country": "US",
                    "line1": f"{i} Main St",
                    "locality": "LA",
                    "region": "CA",
                    "postalCode": "90015",
                },
            }
            results.append(
                {
                    "id": str(i),
                    "prices": [
                        {
                            "fuelProduct": "premium_gas",
                            "credit": {"price": 7 - i, "postedTime": datetime.now(UTC).isoformat()},
                        }
                    ],
                }
            )
        return state, {"results": results, "cursor": {"next": None}}

    async with httpx.AsyncClient() as client:
        provider = GasBuddyWebProvider(client, snapshot_loader=snapshot, transport="http")
        result = await provider.prices(GasBuddySearch(search="Los Angeles, CA", max_results=1))
    assert result.prices[0].name == "Costco"
    assert result.prices[0].membership_required == "costco"
    assert result.partial


async def test_cash_only_costco_credit_fallback_is_excluded():
    async def snapshot(query, url, fuel):
        return {
            "Station:costco": {
                "name": "Costco",
                "priceUnit": "dollars_per_gallon",
                "address": {
                    "country": "US",
                    "line1": "100 Main St",
                    "locality": "LA",
                    "region": "CA",
                    "postalCode": "90015",
                },
            }
        }, {
            "results": [
                {
                    "id": "costco",
                    "prices": [
                        {
                            "fuelProduct": "premium_gas",
                            "credit": {"price": 5, "postedTime": datetime.now(UTC).isoformat()},
                        }
                    ],
                }
            ],
            "cursor": {"next": None},
        }

    async with httpx.AsyncClient() as client:
        provider = GasBuddyWebProvider(client, snapshot_loader=snapshot, transport="http")
        cash = await provider.prices(GasBuddySearch(postal_code="90015", payment_type="cash"))
        credit = await provider.prices(GasBuddySearch(postal_code="90015", payment_type="credit"))
    assert cash.prices == []
    assert credit.prices[0].payment_type == "credit"
    assert credit.prices[0].membership_required == "costco"
