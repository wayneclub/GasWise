import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gaswise.models import Point, Search
from gaswise.providers.anonymous_session import GasBuddyAnonymousSession
from gaswise.providers.base import ProviderError

QUERY = Search(origin=Point(lat=34.04, lng=-118.27), postal_code="90015")
URL = "https://www.gasbuddy.com/home?search=90015&fuel=3&method=credit&maxAge=0"


def fixture_worker(ok=True, data=None, error=None):
    data = data or {"data": {"locationBySearchTerm": {"stations": {"results": []}}}}
    response = SimpleNamespace(ok=ok, json=AsyncMock(return_value=data))
    context = SimpleNamespace(
        request=SimpleNamespace(post=AsyncMock(return_value=response, side_effect=error)), close=AsyncMock()
    )
    worker = GasBuddyAnonymousSession(session_seconds=60)
    worker._bootstrap = AsyncMock(
        return_value=(context, {"Station:1": {}}, {"operationName": "SearchPrices"}, "fixture-csrf")
    )
    return worker, context


async def test_same_query_reuses_session_and_fetches_new_prices_via_http():
    worker, context = fixture_worker()
    first = await worker.snapshot(QUERY, URL, 3)
    second = await worker.snapshot(QUERY, URL, 3)
    assert first == second
    worker._bootstrap.assert_awaited_once()
    assert context.request.post.await_count == 2
    context.close.assert_not_awaited()
    call = context.request.post.call_args.kwargs
    assert call["headers"]["gbcsrf"] == "fixture-csrf"
    assert call["headers"]["Origin"] == "https://www.gasbuddy.com"
    await worker.close()
    context.close.assert_awaited_once()
    assert worker._csrf is None and worker._state is None


@pytest.mark.parametrize(
    "change", [{"postal_code": "90016"}, {"fuel_type": "regular"}, {"payment_type": "cash"}]
)
async def test_changed_search_discards_old_session(change):
    worker, context = fixture_worker()
    await worker.snapshot(QUERY, URL, 3)
    await worker.snapshot(QUERY.model_copy(update=change), URL, 1 if "fuel_type" in change else 3)
    assert worker._bootstrap.await_count == 2
    context.close.assert_awaited_once()
    await worker.close()


async def test_age_limit_renews_session_without_caching_prices():
    worker, context = fixture_worker()
    await worker.snapshot(QUERY, URL, 3)
    worker._created_at -= 61
    await worker.snapshot(QUERY, URL, 3)
    assert worker._bootstrap.await_count == 2
    assert context.request.post.await_count == 2
    await worker.close()


async def test_rejected_http_invalidates_without_retry_or_price_fallback():
    worker, context = fixture_worker(ok=False)
    with pytest.raises(ProviderError, match="gasbuddy_session_http_rejected"):
        await worker.snapshot(QUERY, URL, 3)
    context.request.post.assert_awaited_once()
    context.close.assert_awaited_once()
    assert worker._context is None and worker._csrf is None


async def test_graphql_error_invalidates_session():
    worker, context = fixture_worker(data={"errors": [{"message": "fixture"}]})
    with pytest.raises(ProviderError, match="gasbuddy_session_query_rejected"):
        await worker.snapshot(QUERY, URL, 3)
    context.close.assert_awaited_once()


async def test_cancellation_invalidates_and_cleans_context():
    worker, context = fixture_worker(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await worker.snapshot(QUERY, URL, 3)
    context.close.assert_awaited_once()


async def test_idle_expiry_evicts_credentials_without_another_query():
    worker, context = fixture_worker()
    worker.session_seconds = 0.01
    closed = asyncio.Event()
    context.close.side_effect = lambda: closed.set()
    await worker.snapshot(QUERY, URL, 3)
    await asyncio.wait_for(closed.wait(), timeout=0.5)
    assert worker._context is None and worker._csrf is None
    assert worker._state is None and worker._expiry_task is None
