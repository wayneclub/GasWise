"""Count actual outgoing provider requests against the shared database budget."""

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.shared_cache import (
    acquisition_purpose,
    background_acquisition,
    collection_attempt,
    mandatory_acquisition,
)


def retry_seconds(headers):
    value = headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class RequestBudget:
    def __init__(self, store, limits, background_daily_limit=100, *, sleep=asyncio.sleep, clock=monotonic):
        self.store, self.limits = store, limits
        self.background_daily_limit = background_daily_limit
        self.sleep, self.clock = sleep, clock

    async def before(self, source):
        deadline = self.clock() + 360
        while True:
            try:
                if background_acquisition.get():
                    await self.store.consume(source, self.limits[source], background=True,
                                             background_daily_limit=self.background_daily_limit,
                                             **({"mandatory": True} if mandatory_acquisition.get() else {}),
                                             **({"purpose": acquisition_purpose.get()}
                                                if acquisition_purpose.get() != "demand" else {}))
                else:
                    await self.store.consume(source, self.limits[source])
                trace = collection_attempt.get()
                if trace is not None:
                    trace['http_requests'] = trace.get('http_requests', 0) + 1
                    trace['http_status'] = None
                    trace.setdefault('phase', 'source_http')
                return
            except ProviderError as error:
                # Only local minute-budget exhaustion may wait. Never retry a
                # rejected HTTP request, daily cap, cooldown or unavailable DB.
                if not (background_acquisition.get() and source == "gasbuddy"
                        and str(error) in {f"{source}_background_budget_exhausted",
                                           f"{source}_request_budget_exhausted"}):
                    raise
                try:
                    state = await self.store.budget_state(source)
                except Exception:
                    raise ProviderError("shared_pricing_budget_unavailable") from None
                if state.get("blocked_seconds", 0) or state["background_day_used"] >= (state.get("daily_limit") or self.background_daily_limit):
                    raise
                delay = min(60, max(.1, float(state.get("window_seconds", 60)) + .05))
                if self.clock() + delay > deadline:
                    raise ProviderError(f"{source}_background_wait_exhausted") from None
                await self.sleep(delay)
            except Exception:
                raise ProviderError("shared_pricing_budget_unavailable") from None

    async def after(self, source, response):
        trace = collection_attempt.get()
        if trace is not None:
            trace['http_status'] = response.status_code
        if response.status_code not in (401, 403, 429) and response.headers.get("cf-mitigated") != "challenge":
            return
        try:
            await self.store.cooldown(source, retry_seconds(response.headers))
        except Exception:
            raise ProviderError("shared_pricing_budget_unavailable") from None
        raise ProviderError(f"{source}_rate_limited" if response.status_code == 429 else f"{source}_access_rejected_cooldown")
