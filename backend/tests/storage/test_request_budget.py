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


async def test_background_http_requests_use_separate_shared_allowance():
    from gaswise.domain.pricing.shared_cache import background_acquisition

    class Store:
        calls = []

        async def consume(self, source, limit, **options):
            self.calls.append((source, limit, options))

    store = Store()
    budget = RequestBudget(store, {"maps": 60}, background_daily_limit=40)
    token = background_acquisition.set(True)
    try:
        await budget.before("maps")
    finally:
        background_acquisition.reset(token)
    await budget.before("maps")
    assert store.calls == [("maps", 60, {"background": True, "background_daily_limit": 40}),
                           ("maps", 60, {})]


async def test_background_minute_wait_does_not_retry_daily_limit_or_foreground():
    from gaswise.domain.pricing.shared_cache import background_acquisition

    class Store:
        error = "gasbuddy_background_budget_exhausted"
        calls = 0

        async def consume(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError(self.error)

        async def budget_state(self, source):
            return {"window_seconds": 30, "blocked_seconds": 0, "background_day_used": 0}

    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)

    store = Store()
    budget = RequestBudget(store, {"gasbuddy": 12}, sleep=sleep)
    token = background_acquisition.set(True)
    try:
        await budget.before("gasbuddy")
        assert store.calls == 2 and sleeps == [30.05]
        store.calls = 0
        store.error = "gasbuddy_background_daily_budget_exhausted"
        with pytest.raises(ProviderError, match="daily_budget"):
            await budget.before("gasbuddy")
        assert store.calls == 1 and sleeps == [30.05]
    finally:
        background_acquisition.reset(token)
    store.calls = 0
    store.error = "gasbuddy_request_budget_exhausted"
    with pytest.raises(ProviderError, match="request_budget"):
        await budget.before("gasbuddy")
    assert store.calls == 1


async def test_background_wait_has_deadline_and_respects_shared_cooldown():
    from gaswise.domain.pricing.shared_cache import background_acquisition

    class Store:
        blocked = 0
        async def consume(self, *args, **kwargs):
            raise ProviderError("gasbuddy_background_budget_exhausted")
        async def budget_state(self, source):
            return {"window_seconds": 60, "blocked_seconds": self.blocked, "background_day_used": 0}

    now, sleeps = [0], []
    async def sleep(delay):
        sleeps.append(delay)
        now[0] += delay
    store = Store()
    budget = RequestBudget(store, {"gasbuddy": 12}, sleep=sleep, clock=lambda: now[0])
    token = background_acquisition.set(True)
    try:
        with pytest.raises(ProviderError, match="wait_exhausted"):
            await budget.before("gasbuddy")
        assert sleeps == [60, 60, 60, 60, 60, 60]
        store.blocked = 120
        with pytest.raises(ProviderError, match="background_budget"):
            await budget.before("gasbuddy")
        assert len(sleeps) == 6
    finally:
        background_acquisition.reset(token)
