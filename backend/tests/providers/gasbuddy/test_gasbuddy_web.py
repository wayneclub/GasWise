from datetime import UTC, datetime

import httpx
import pytest

from gaswise.contracts.search import Search
from gaswise.domain.ports import ProviderError
from gaswise.providers.gasbuddy.web import GasBuddyWebProvider
from tests.support.gasbuddy_web import (
    ORIGIN as ORIGIN,
)
from tests.support.gasbuddy_web import (
    transport as transport,
)


async def test_reads_credit_price_not_cheaper_cash_and_preserves_timestamp():
    timestamp = datetime.now(UTC).isoformat()
    async with httpx.AsyncClient(transport=transport(timestamp=timestamp)) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert str(result.prices[0].price_per_gallon) == "6.95"
    assert result.prices[0].payment_type == "credit"
    assert result.prices[0].price_updated_at.isoformat() == timestamp
    assert result.prices[0].octane is None
    assert result.prices[0].report_kind == "datafeed"


async def test_no_credit_never_falls_back_to_cash():
    async with httpx.AsyncClient(transport=transport(credit=False)) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert result.prices == []


async def test_cash_never_falls_back_to_credit():
    async with httpx.AsyncClient(transport=transport(cash=False)) as client:
        result = await GasBuddyWebProvider(client).prices(
            Search(origin=ORIGIN, postal_code="90015", payment_type="cash")
        )
    assert result.prices == []


async def test_explicit_cash_returns_only_cash():
    async with httpx.AsyncClient(transport=transport()) as client:
        result = await GasBuddyWebProvider(client).prices(
            Search(origin=ORIGIN, postal_code="90015", payment_type="cash")
        )
    assert result.prices and all(row.payment_type == "cash" for row in result.prices)


async def test_zero_missing_price_is_not_a_free_station():
    async with httpx.AsyncClient(transport=transport(price=0)) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert result.prices == []


async def test_unknown_source_time_stays_unknown_after_fetch():
    async with httpx.AsyncClient(transport=transport()) as client:
        result = await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))
    assert result.prices[0].price_updated_at is None


async def test_block_is_explicit_and_does_not_fabricate_data():
    async with httpx.AsyncClient(transport=transport(blocked=True)) as client:
        with pytest.raises(ProviderError, match="gasbuddy_web_access_rejected"):
            await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))


async def test_schema_change_is_not_empty_success():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="changed"))
    ) as client:
        with pytest.raises(ProviderError, match="gasbuddy_web_schema_changed"):
            await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN, postal_code="90015"))


async def test_postal_code_is_required_for_website_search():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderError, match="gasbuddy_postal_code_required"):
            await GasBuddyWebProvider(client).prices(Search(origin=ORIGIN))


async def test_payment_variants_are_acquired_in_one_search_and_keep_both_conditions():
    from gaswise.contracts.sources import GasBuddySearch
    async with httpx.AsyncClient(transport=transport()) as client:
        result = await GasBuddyWebProvider(client).prices(GasBuddySearch(postal_code="90015", fuel_type="premium", payment_type="cash_or_credit", include_payment_variants=True, max_results=1))
    assert {q.payment_type for q in result.prices} == {"cash", "credit"}
    assert len(result.prices) == 2
    assert not result.partial
