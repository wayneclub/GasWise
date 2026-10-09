from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError
from test_gasbuddy_web import transport

from gaswise.models import GasBuddySearch, gasbuddy_variables
from gaswise.providers.gasbuddy_web import GasBuddyWebProvider


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
