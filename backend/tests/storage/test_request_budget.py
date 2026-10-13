from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from gaswise.domain.ports import ProviderError
from gaswise.providers.storage.request_budget import RequestBudget, retry_seconds


def test_retry_after_seconds_and_http_date():
    assert retry_seconds({"Retry-After":"300"}) == 300
    assert retry_seconds({"Retry-After":"invalid"}) is None
    assert 298 <= retry_seconds({"Retry-After":format_datetime(datetime.now(UTC)+timedelta(seconds=300))}) <= 300


async def test_request_budget_counts_requests_and_honors_rejection_cooldown():
    class Store:
        calls = []
        async def consume(self,source,limit):
            self.calls.append((source,limit))
        async def cooldown(self,source,seconds):
            self.calls.append((source,seconds))
    store = Store()
    budget = RequestBudget(store,{"maps":60})
    await budget.before("maps")
    await budget.after("maps",httpx.Response(200))
    with pytest.raises(ProviderError,match="rate_limited"):
        await budget.after("maps",httpx.Response(429,headers={"Retry-After":"900"}))
    assert store.calls == [("maps",60),("maps",900)]
    with pytest.raises(ProviderError,match="access_rejected_cooldown"):
        await budget.after("maps",httpx.Response(200,headers={"cf-mitigated":"challenge"}))


async def test_budget_database_failure_does_not_allow_unbudgeted_network_access():
    class Broken:
        async def consume(self,*args):
            raise RuntimeError("private connection error")
    with pytest.raises(ProviderError,match="shared_pricing_budget_unavailable"):
        await RequestBudget(Broken(),{"waze":20}).before("waze")
